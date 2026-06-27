from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import CacheEntry, CacheStat


def serialize_entry(entry: CacheEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "namespace": entry.namespace,
        "key": entry.cache_key,
        "value": json.loads(entry.value_json),
        "hits": entry.hits,
        "expires_at": entry.expires_at,
        "created_at": entry.created_at,
        "last_accessed_at": entry.last_accessed_at,
    }


class CacheService:
    """Zero-cost cache layer (Missao 43 - Cache Inteligente).

    Backend padrao e SQLite, no mesmo espirito do QueueService (Missao 42):
    comeca local e zero-custo, mas o contrato publico (get/set/delete/
    invalidate_namespace/clear/stats) e generico o suficiente para um
    backend real (KeyDB/Redis) mais tarde, sem mudar quem chama.

    Importante: todas as comparacoes de data/hora (expiracao, LRU) sao feitas
    via filtro SQL (`Coluna <= now`), nunca comparando um datetime python ja
    lido de volta do SQLite contra um datetime "novo" - colunas DATETIME do
    SQLite voltam *naive* (sem tzinfo) depois de uma query, e comparar isso
    contra um `datetime.now(UTC)` (aware) lanca TypeError em python puro. Em
    filtros SQL isso nao acontece, pois a comparacao e textual/lexicografica
    e ambos os lados sao sempre escritos no mesmo formato (UTC aware
    isoformat) - o mesmo padrao ja usado em QueueService.claim().
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def _stat(self, namespace: str) -> CacheStat:
        stat = self.db.query(CacheStat).filter(CacheStat.namespace == namespace).first()
        if stat is None:
            stat = CacheStat(namespace=namespace)
            self.db.add(stat)
            self.db.commit()
            self.db.refresh(stat)
        return stat

    def get(self, key: str, *, namespace: str = "default") -> Any | None:
        """Retorna o valor em cache, ou None em miss/expirado.

        Limitacao deliberada: nao ha como distinguir "miss" de "valor
        armazenado e None" por este metodo - quem precisa dessa distincao
        deve usar `get_entry()` (retorna o CacheEntry ou None)."""
        entry = self._lookup_live_entry(key, namespace=namespace)
        if entry is None:
            return None
        return json.loads(entry.value_json)

    def get_entry(self, key: str, *, namespace: str = "default") -> CacheEntry | None:
        return self._lookup_live_entry(key, namespace=namespace)

    def _lookup_live_entry(self, key: str, *, namespace: str) -> CacheEntry | None:
        now = datetime.now(UTC)
        stat = self._stat(namespace)

        live_entry = (
            self.db.query(CacheEntry)
            .filter(
                CacheEntry.namespace == namespace,
                CacheEntry.cache_key == key,
                or_(CacheEntry.expires_at.is_(None), CacheEntry.expires_at > now),
            )
            .first()
        )
        if live_entry is not None:
            live_entry.hits += 1
            live_entry.last_accessed_at = now
            stat.total_hits += 1
            self.db.commit()
            self.db.refresh(live_entry)
            return live_entry

        # Miss: pode ser "nunca existiu" ou "existia mas expirou". No segundo
        # caso, faz o purge lazy da linha morta (nao deixa lixo acumular so
        # por causa de leituras).
        dead_entry = (
            self.db.query(CacheEntry)
            .filter(CacheEntry.namespace == namespace, CacheEntry.cache_key == key)
            .first()
        )
        stat.total_misses += 1
        if dead_entry is not None:
            self.db.delete(dead_entry)
            stat.total_expired_purged += 1
        self.db.commit()
        return None

    def set(self, key: str, value: Any, *, namespace: str = "default", ttl_seconds: int | None = None) -> CacheEntry:
        """Grava (ou substitui) um valor em cache.

        ttl_seconds=None usa o default da configuracao
        (`cache_default_ttl_seconds`). ttl_seconds<=0 e um pedido explicito
        de "sem expiracao" (fica em cache ate ser removido, invalidado ou
        evitado por LRU) - diferente do default da configuracao, que precisa
        ser >=1 (validate_settings)."""
        now = datetime.now(UTC)
        if ttl_seconds is None:
            ttl_seconds = self.settings.cache_default_ttl_seconds
        expires_at = None if ttl_seconds <= 0 else now + timedelta(seconds=ttl_seconds)

        entry = (
            self.db.query(CacheEntry)
            .filter(CacheEntry.namespace == namespace, CacheEntry.cache_key == key)
            .first()
        )
        if entry is None:
            entry = CacheEntry(namespace=namespace, cache_key=key, hits=0)
            self.db.add(entry)
        entry.value_json = json.dumps(value, ensure_ascii=False)
        entry.expires_at = expires_at
        entry.last_accessed_at = now
        # hits NAO e resetado num set() sobre uma chave existente: representa
        # "quantas vezes esse valor foi lido", nao "quantas vezes foi escrito".

        stat = self._stat(namespace)
        stat.total_sets += 1
        self.db.commit()
        self.db.refresh(entry)

        self._evict_if_over_capacity(namespace)
        self.db.refresh(entry)
        return entry

    def _evict_if_over_capacity(self, namespace: str) -> int:
        """Politica LRU: remove as entradas menos recentemente acessadas da
        namespace até caber em `cache_max_entries_per_namespace`. Retorna
        quantas entradas foram evitadas."""
        max_entries = self.settings.cache_max_entries_per_namespace
        count = self.db.query(CacheEntry).filter(CacheEntry.namespace == namespace).count()
        overflow = count - max_entries
        if overflow <= 0:
            return 0

        victims = (
            self.db.query(CacheEntry)
            .filter(CacheEntry.namespace == namespace)
            .order_by(CacheEntry.last_accessed_at.asc())
            .limit(overflow)
            .all()
        )
        for victim in victims:
            self.db.delete(victim)

        stat = self._stat(namespace)
        stat.total_evictions += len(victims)
        self.db.commit()
        return len(victims)

    def delete(self, key: str, *, namespace: str = "default") -> bool:
        entry = (
            self.db.query(CacheEntry)
            .filter(CacheEntry.namespace == namespace, CacheEntry.cache_key == key)
            .first()
        )
        if entry is None:
            return False
        self.db.delete(entry)
        self.db.commit()
        return True

    def invalidate_namespace(self, namespace: str) -> int:
        """Remove todas as entradas de uma namespace de uma vez - invalidacao
        em lote, ex.: depois de atualizar a fonte de dados que essa namespace
        representa, sem precisar saber as chaves individuais."""
        entries = self.db.query(CacheEntry).filter(CacheEntry.namespace == namespace).all()
        count = len(entries)
        for entry in entries:
            self.db.delete(entry)
        self.db.commit()
        return count

    def clear(self) -> int:
        count = self.db.query(CacheEntry).count()
        self.db.query(CacheEntry).delete()
        self.db.commit()
        return count

    def purge_expired(self, *, namespace: str | None = None) -> int:
        """Remove entradas ja expiradas proativamente, sem depender de um
        get() por chave. Util para limpeza periodica (ex.: acionado por um
        job da fila zero-custo)."""
        now = datetime.now(UTC)
        query = self.db.query(CacheEntry).filter(
            CacheEntry.expires_at.isnot(None), CacheEntry.expires_at <= now
        )
        if namespace is not None:
            query = query.filter(CacheEntry.namespace == namespace)
        entries = query.all()

        by_namespace: dict[str, int] = {}
        for entry in entries:
            by_namespace[entry.namespace] = by_namespace.get(entry.namespace, 0) + 1
            self.db.delete(entry)
        for ns, removed in by_namespace.items():
            stat = self._stat(ns)
            stat.total_expired_purged += removed
        self.db.commit()
        return len(entries)

    def stats(self, *, namespace: str | None = None) -> dict[str, Any]:
        """Estatisticas cumulativas. Sem `namespace`, agrega todas as
        namespaces ja conhecidas (que tiveram pelo menos um get/set)."""
        now = datetime.now(UTC)
        stat_query = self.db.query(CacheStat)
        if namespace is not None:
            stat_query = stat_query.filter(CacheStat.namespace == namespace)
        stat_rows = stat_query.all()

        total_hits = sum(s.total_hits for s in stat_rows)
        total_misses = sum(s.total_misses for s in stat_rows)
        total_sets = sum(s.total_sets for s in stat_rows)
        total_evictions = sum(s.total_evictions for s in stat_rows)
        total_expired_purged = sum(s.total_expired_purged for s in stat_rows)
        total_requests = total_hits + total_misses
        hit_rate = (total_hits / total_requests) if total_requests > 0 else 0.0

        size_query = self.db.query(CacheEntry)
        if namespace is not None:
            size_query = size_query.filter(CacheEntry.namespace == namespace)
        size = size_query.count()
        live_size = size_query.filter(
            or_(CacheEntry.expires_at.is_(None), CacheEntry.expires_at > now)
        ).count()

        per_namespace: dict[str, dict[str, int]] = {}
        for s in stat_rows:
            ns_size = self.db.query(CacheEntry).filter(CacheEntry.namespace == s.namespace).count()
            per_namespace[s.namespace] = {
                "hits": s.total_hits,
                "misses": s.total_misses,
                "sets": s.total_sets,
                "evictions": s.total_evictions,
                "expired_purged": s.total_expired_purged,
                "size": ns_size,
            }

        return {
            "backend": self.settings.cache_backend,
            "hits": total_hits,
            "misses": total_misses,
            "sets": total_sets,
            "evictions": total_evictions,
            "expired_purged": total_expired_purged,
            "hit_rate": hit_rate,
            "size": size,
            "live_size": live_size,
            "per_namespace": per_namespace,
        }
