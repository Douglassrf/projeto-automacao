from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()


class CampaignMemoryStore:
    """Memória evolutiva local e segura para o CampaignBrainAgent.

    Primeira versão:
    - Usa JSONL local em /logs/campaign_brain_memory.log.
    - Não depende de banco.
    - Não depende de SQLAlchemy.
    - Não chama API externa.
    - Não interfere em MetaCampaignOperator, VideoPipeline ou PremiumRender.
    """

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.logs_dir = logs_dir or project_root / "logs"
        self.memory_file = self.logs_dir / "campaign_brain_memory.log"

    def remember(self, record: dict[str, Any]) -> dict[str, Any]:
        """Registra aprendizado controlado em JSONL local."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        payload = dict(record or {})
        payload.setdefault("recorded_at", datetime.now(UTC).isoformat())
        payload.setdefault("source", "campaign_brain_memory")
        with _LOCK:
            with self.memory_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return {
            "status": "stored",
            "memory_file": str(self.memory_file),
            "recorded_at": payload["recorded_at"],
        }

    def read_all(self, limit: int = 200) -> list[dict[str, Any]]:
        """Lê os registros mais recentes da memória local."""
        if not self.memory_file.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.memory_file.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-limit:]
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

    def summarize(self, product_name: str = "", niche: str = "", limit: int = 200) -> dict[str, Any]:
        """Resume experiências anteriores parecidas."""
        product_key = (product_name or "").lower().strip()
        niche_key = (niche or "").lower().strip()
        records = self.read_all(limit=limit)

        similar: list[dict[str, Any]] = []
        winners: list[dict[str, Any]] = []
        losers: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []

        for item in records:
            item_product = str(item.get("product_name") or "").lower()
            item_niche = str(item.get("niche") or "").lower()
            is_similar = False
            if product_key and product_key in item_product:
                is_similar = True
            if niche_key and niche_key in item_niche:
                is_similar = True
            if not product_key and not niche_key:
                is_similar = True

            if not is_similar:
                continue

            similar.append(item)
            outcome = str(item.get("outcome") or item.get("decision") or "").upper()
            if outcome in {"WINNER", "SCALE", "PROFIT", "LUCRO", "SIM"}:
                winners.append(item)
            elif outcome in {"LOSER", "LOSS", "PREJUIZO", "PREJUÍZO", "NÃO", "NAO"}:
                losers.append(item)
            elif outcome in {"BLOCKED", "BLOQUEADO"}:
                blocked.append(item)

        common_lessons: list[str] = []
        for item in similar[-20:]:
            lesson = item.get("lesson") or item.get("learning") or item.get("reasoning")
            if lesson and lesson not in common_lessons:
                common_lessons.append(str(lesson))

        recommendation = "Sem histórico suficiente. Manter teste conservador em dry_run e orçamento controlado."
        if winners and not losers:
            recommendation = "Há histórico positivo parecido. Prosseguir com cautela e validar em dry_run."
        elif losers and not winners:
            recommendation = "Histórico parecido majoritariamente negativo. Revisar oferta, página, criativo e checkout antes de avançar."
        elif winners and losers:
            recommendation = "Histórico misto. Comparar padrões vencedores e perdedores antes de decidir escala."
        if blocked:
            recommendation = "Há bloqueios anteriores parecidos. Exigir revisão de política, promessa e página antes de qualquer campanha real."

        return {
            "source": str(self.memory_file),
            "available": bool(records),
            "total_records": len(records),
            "similar_records": len(similar),
            "winners": len(winners),
            "losers": len(losers),
            "blocked": len(blocked),
            "recent_lessons": common_lessons[-8:],
            "historical_recommendation": recommendation,
            "last_similar": similar[-3:],
        }
