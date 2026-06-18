from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()


class DecisionFeedStore:
    """DecisionFeed seguro em JSONL para auditoria do CampaignBrainAgent.

    Missão 10:
    - Não depende de banco.
    - Não depende de SQLAlchemy.
    - Não chama API externa.
    - Não publica campanha.
    - Registra decisões do Brain em log local.
    """

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.logs_dir = logs_dir or project_root / "logs"
        self.feed_file = self.logs_dir / "decision_feed.log"

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": "DecisionFeedStore",
            "mode": "local_jsonl_audit",
            "storage": str(self.feed_file),
            "can_publish": False,
            "can_call_external_api": False,
            "database_required": False,
        }

    def record_brain_decision(self, review: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "source": "CampaignBrainAgent",
            "product_name": context.get("product_name") or review.get("product_name") or "Produto sem nome",
            "niche": context.get("niche") or context.get("nicho") or "",
            "campaign_stage": review.get("campaign_stage") or context.get("campaign_stage") or "V1",
            "decision": review.get("decision"),
            "confidence": review.get("confidence"),
            "next_action": review.get("next_action"),
            "positive_points": review.get("positive_points", []),
            "negative_points": review.get("negative_points", []),
            "blocked_reasons": review.get("blocked_reasons", []),
            "meta_risk": review.get("meta_risk", {}),
            "historical_recommendation": review.get("historical_recommendation", ""),
            "panoramic_view": review.get("panoramic_view", ""),
            "recommended_solution": review.get("recommended_solution", ""),
            "memory_used_keys": sorted(list((review.get("memory_used") or {}).keys())),
        }
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with self.feed_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {
            "status": "stored",
            "agent": "DecisionFeedStore",
            "storage": str(self.feed_file),
            "record": record,
        }


    def record_learning_loop_decision(self, loop_result: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Registra decisão/aprendizado vindo do LearningLoop.

        Não publica campanha, não chama API externa e não depende de banco.
        """
        context = context or {}
        variations = loop_result.get("generated_variations", []) or []
        winners = loop_result.get("winners", []) or []
        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "source": "LearningLoop",
            "product_name": context.get("product_name") or loop_result.get("product_name") or "Produto sem nome",
            "niche": context.get("niche") or context.get("nicho") or "",
            "campaign_stage": context.get("campaign_stage") or "V4_V5_V6",
            "decision": "SIM" if variations else "NÃO",
            "confidence": 88 if variations and winners else 55,
            "next_action": "brain_review_dry_run" if variations else "coletar_mais_eventos",
            "positive_points": [
                f"LearningLoop gerou {len(variations)} variações.",
                f"LearningLoop identificou {len(winners)} criativo(s) vencedor(es).",
                f"Eventos usados: {loop_result.get('total_events_used', 0)}.",
            ],
            "negative_points": loop_result.get("warnings", []),
            "blocked_reasons": [],
            "meta_risk": {},
            "historical_recommendation": "Usar o Brain para revisar V4/V5/V6 antes de qualquer dry_run de campanha.",
            "panoramic_view": "LearningLoop transformou eventos de conversão em variações reutilizáveis para as próximas fases.",
            "recommended_solution": "Registrar aprendizado, revisar pelo Brain e manter próxima ação em dry_run.",
            "memory_used_keys": ["capi_events", "learning_loop", "campaign_memory", "decision_feed"],
            "learning_loop_summary": {
                "capi_stable": loop_result.get("capi_stable"),
                "total_events_used": loop_result.get("total_events_used"),
                "winners_count": len(winners),
                "variations": [item.get("version") for item in variations],
                "output_folder": loop_result.get("output_folder"),
            },
        }
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with self.feed_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {
            "status": "stored",
            "agent": "DecisionFeedStore",
            "storage": str(self.feed_file),
            "record": record,
        }

    def list_decisions(self, limit: int = 50) -> dict[str, Any]:
        records = self._read(limit=limit)
        return {
            "status": "ok",
            "agent": "DecisionFeedStore",
            "storage": str(self.feed_file),
            "count": len(records),
            "decisions": records,
        }

    def summary(self, limit: int = 200) -> dict[str, Any]:
        records = self._read(limit=limit)
        total = len(records)
        yes = sum(1 for item in records if str(item.get("decision")).upper() == "SIM")
        no = sum(1 for item in records if str(item.get("decision")).upper() in {"NÃO", "NAO"})
        dry_run = sum(1 for item in records if item.get("next_action") == "dry_run")
        blocked = sum(1 for item in records if item.get("next_action") == "bloquear_e_revisar" or item.get("blocked_reasons"))
        avg_conf = round(sum(float(item.get("confidence") or 0) for item in records) / total, 2) if total else 0

        status = "empty"
        headline = "Sem decisões registradas"
        next_action = "Rode /brain/review/mock ou /campaign/dry-run/mock para gerar decisões."
        if total:
            status = "healthy" if no == 0 and blocked == 0 else "attention"
            headline = "Decisões registradas com rastreabilidade."
            next_action = "Revisar decisões bloqueadas antes de escalar." if blocked else "Manter dry_run e observar métricas."

        return {
            "status": "ok",
            "agent": "DecisionFeedStore",
            "total": total,
            "decision_yes": yes,
            "decision_no": no,
            "dry_run": dry_run,
            "blocked_or_review": blocked,
            "average_confidence": avg_conf,
            "health": status,
            "headline": headline,
            "next_action": next_action,
        }

    def _read(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.feed_file.exists():
            return []
        with self.feed_file.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-limit:]
        records: list[dict[str, Any]] = []
        for line in lines:
            try:
                item = json.loads(line.strip())
                if isinstance(item, dict):
                    records.append(item)
            except json.JSONDecodeError:
                continue
        return records
