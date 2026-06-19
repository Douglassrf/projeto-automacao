from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()


class MetaUpdateWatcher:
    """Agente seguro para registrar e consultar atualizações da Meta.

    Missão 08:
    - Não faz login.
    - Não usa Selenium.
    - Não chama API Meta.
    - Não publica campanha.
    - Não altera orçamento.
    - Não interfere em MetaCampaignOperator.
    - Usa armazenamento local JSONL controlado.
    """

    DEFAULT_SOURCES = [
        "Meta Advertising Standards",
        "Meta Business Help Center",
        "Meta Marketing API changelog",
        "Meta Developers",
    ]

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.logs_dir = logs_dir or project_root / "logs"
        self.update_file = self.logs_dir / "meta_updates.log"

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": "MetaUpdateWatcher",
            "mode": "manual_safe_registry",
            "can_login": False,
            "can_publish": False,
            "can_call_meta_api": False,
            "can_use_selenium": False,
            "storage": str(self.update_file),
        }

    def register_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Registra uma atualização de política/plataforma em memória local."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "id": payload.get("id") or self._make_id(payload),
            "date": payload.get("date") or datetime.now(UTC).date().isoformat(),
            "source": payload.get("source") or "manual",
            "source_url": payload.get("source_url") or "",
            "summary": payload.get("summary") or "Atualização registrada sem resumo detalhado.",
            "risk_level": self._normalize_risk(payload.get("risk_level") or payload.get("risk") or "low"),
            "affected_topics": payload.get("affected_topics") or payload.get("topics") or [],
            "recommended_action": payload.get("recommended_action") or "Revisar campanha em dry_run antes de qualquer publicação.",
            "registered_at": datetime.now(UTC).isoformat(),
            "source_type": "manual_or_controlled",
        }
        with _LOCK:
            with self.update_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {
            "status": "stored",
            "agent": "MetaUpdateWatcher",
            "record": record,
            "storage": str(self.update_file),
        }

    def list_updates(self, limit: int = 50) -> dict[str, Any]:
        records = self._read_updates(limit=limit)
        return {
            "status": "ok",
            "agent": "MetaUpdateWatcher",
            "storage": str(self.update_file),
            "count": len(records),
            "updates": records,
        }

    def assess_context(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Avalia se existem atualizações relacionadas ao produto/nicho."""
        context = context or {}
        product_name = str(context.get("product_name") or "").lower()
        niche = str(context.get("niche") or context.get("nicho") or "").lower()
        copy = str(context.get("copy") or "").lower()
        offer = str(context.get("offer") or "").lower()
        haystack = " ".join([product_name, niche, copy, offer])

        updates = self._read_updates(limit=200)
        related: list[dict[str, Any]] = []
        highest_risk = "low"
        for item in updates:
            topics = [str(topic).lower() for topic in item.get("affected_topics", [])]
            summary = str(item.get("summary") or "").lower()
            is_related = False
            if not topics and not haystack:
                is_related = True
            for topic in topics:
                if topic and topic in haystack:
                    is_related = True
            if niche and niche in summary:
                is_related = True
            if product_name and product_name in summary:
                is_related = True

            if is_related:
                related.append(item)
                highest_risk = self._max_risk(highest_risk, item.get("risk_level", "low"))

        recommendation = "Nenhuma atualização relacionada encontrada. Manter revisão padrão em dry_run."
        should_block = False
        if highest_risk == "medium":
            recommendation = "Há atualização relacionada de risco médio. Revisar copy, criativo e página antes de publicar."
        if highest_risk == "high":
            recommendation = "Há atualização relacionada de alto risco. Bloquear publicação real até revisão manual."
            should_block = True

        return {
            "status": "ok",
            "agent": "MetaUpdateWatcher",
            "mode": "manual_safe_registry",
            "updates_available": bool(updates),
            "related_updates_count": len(related),
            "highest_risk": highest_risk,
            "should_block_real_publish": should_block,
            "recommendation": recommendation,
            "related_updates": related[-10:],
        }

    def mock_update(self) -> dict[str, Any]:
        """Registra atualização mockada para teste seguro."""
        return self.register_update({
            "source": "Meta manual review / mock",
            "source_url": "https://transparency.meta.com/policies/ad-standards/",
            "summary": "Atualização mockada: nichos sensíveis como emagrecimento exigem revisão de promessa, criativo e página antes de publicação real.",
            "risk_level": "medium",
            "affected_topics": ["emagrecimento", "saúde", "promessa", "criativo"],
            "recommended_action": "Manter campanha em dry_run e revisar copy para evitar promessas absolutas.",
        })

    def _read_updates(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.update_file.exists():
            return []
        with self.update_file.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-limit:]
        records: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    records.append(item)
            except json.JSONDecodeError:
                continue
        return records

    @staticmethod
    def _normalize_risk(value: Any) -> str:
        risk = str(value or "low").lower()
        if risk in {"alto", "high", "critical", "critico", "crítico"}:
            return "high"
        if risk in {"medio", "médio", "medium", "moderate"}:
            return "medium"
        return "low"

    @staticmethod
    def _max_risk(current: str, candidate: str) -> str:
        order = {"low": 1, "medium": 2, "high": 3}
        candidate = MetaUpdateWatcher._normalize_risk(candidate)
        return candidate if order[candidate] > order.get(current, 1) else current

    @staticmethod
    def _make_id(payload: dict[str, Any]) -> str:
        raw = "|".join([
            str(payload.get("date") or datetime.now(UTC).date().isoformat()),
            str(payload.get("source") or "manual"),
            str(payload.get("summary") or "")[:40],
        ])
        safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw).strip("-")
        while "--" in safe:
            safe = safe.replace("--", "-")
        return safe[:80] or "meta-update"
