from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


class CampaignIntelligenceSafe:
    """Inteligência comparativa segura baseada nos logs locais do projeto.

    Missão 11:
    - Não depende de banco/SQLAlchemy.
    - Não chama API externa.
    - Não publica campanha.
    - Lê DecisionFeed e CampaignMemory para identificar padrões.
    """

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.logs_dir = logs_dir or project_root / "logs"
        self.decision_feed_file = self.logs_dir / "decision_feed.log"
        self.memory_file = self.logs_dir / "campaign_brain_memory.log"

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": "CampaignIntelligenceSafe",
            "mode": "local_logs_comparative_intelligence",
            "database_required": False,
            "external_api": False,
            "sources": {
                "decision_feed": str(self.decision_feed_file),
                "campaign_memory": str(self.memory_file),
            },
        }

    def analyze(self, product_name: str = "", niche: str = "", limit: int = 300) -> dict[str, Any]:
        decisions = self._read_jsonl(self.decision_feed_file, limit=limit)
        memories = self._read_jsonl(self.memory_file, limit=limit)

        product_key = product_name.lower().strip()
        niche_key = niche.lower().strip()

        filtered_decisions = [item for item in decisions if self._match(item, product_key, niche_key)]
        filtered_memories = [item for item in memories if self._match(item, product_key, niche_key)]

        stage_counter = Counter(str(item.get("campaign_stage") or "unknown") for item in filtered_decisions + filtered_memories)
        decision_counter = Counter(str(item.get("decision") or item.get("outcome") or "unknown").upper() for item in filtered_decisions + filtered_memories)
        next_action_counter = Counter(str(item.get("next_action") or "unknown") for item in filtered_decisions)

        positive_phrases = Counter()
        negative_phrases = Counter()
        lessons = []
        metric_totals: dict[str, list[float]] = defaultdict(list)

        for item in filtered_decisions:
            for point in item.get("positive_points", []) or []:
                positive_phrases[str(point)] += 1
            for point in item.get("negative_points", []) or []:
                negative_phrases[str(point)] += 1

        for item in filtered_memories:
            lesson = item.get("lesson") or item.get("learning") or item.get("reasoning")
            if lesson:
                lessons.append(str(lesson))
            metrics = item.get("metrics") or {}
            if isinstance(metrics, dict):
                for key, value in metrics.items():
                    try:
                        metric_totals[key].append(float(value))
                    except (TypeError, ValueError):
                        continue

        metric_averages = {
            key: round(sum(values) / len(values), 2)
            for key, values in metric_totals.items()
            if values
        }

        winners = decision_counter.get("WINNER", 0) + decision_counter.get("SIM", 0) + decision_counter.get("SCALE", 0)
        losers = decision_counter.get("LOSER", 0) + decision_counter.get("NÃO", 0) + decision_counter.get("NAO", 0) + decision_counter.get("LOSS", 0)

        recommendation = "Sem dados comparativos suficientes. Manter V1/V2 conservador e registrar mais decisões."
        if filtered_decisions or filtered_memories:
            recommendation = "Há dados comparativos. Usar dry_run e priorizar padrões positivos mais frequentes."
        if losers > winners:
            recommendation = "Histórico negativo supera positivo. Revisar oferta, página, copy e checkout antes de avançar."
        if winners > losers and winners > 0:
            recommendation = "Histórico positivo superior. Prosseguir com teste controlado e observar gargalos antes de escalar."

        return {
            "status": "ok",
            "agent": "CampaignIntelligenceSafe",
            "mode": "comparative_local",
            "filters": {
                "product_name": product_name,
                "niche": niche,
            },
            "source_counts": {
                "decision_feed_total": len(decisions),
                "campaign_memory_total": len(memories),
                "decision_feed_matched": len(filtered_decisions),
                "campaign_memory_matched": len(filtered_memories),
            },
            "stage_distribution": dict(stage_counter.most_common()),
            "decision_distribution": dict(decision_counter.most_common()),
            "next_action_distribution": dict(next_action_counter.most_common()),
            "metric_averages": metric_averages,
            "top_positive_patterns": positive_phrases.most_common(8),
            "top_negative_patterns": negative_phrases.most_common(8),
            "recent_lessons": lessons[-8:],
            "winners": winners,
            "losers": losers,
            "recommendation": recommendation,
        }

    def mock_seed(self) -> dict[str, Any]:
        """Cria dados locais mínimos para testar inteligência comparativa."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        memory_records = [
            {
                "product_name": "Ebook de Receitas Fitness",
                "niche": "emagrecimento",
                "campaign_stage": "V1",
                "outcome": "WINNER",
                "lesson": "Copy moderada com foco em praticidade gerou melhor sinal inicial.",
                "metrics": {"connect_rate": 82, "checkout_rate": 25.61, "purchase_rate": 3.41, "roas": 1.8},
                "source": "CampaignIntelligenceSafe.mock_seed",
            },
            {
                "product_name": "Ebook de Receitas Fitness",
                "niche": "emagrecimento",
                "campaign_stage": "V1",
                "outcome": "LOSER",
                "lesson": "Promessa agressiva aumentou risco e não deve ser repetida.",
                "metrics": {"connect_rate": 48, "checkout_rate": 8, "purchase_rate": 0, "roas": 0},
                "source": "CampaignIntelligenceSafe.mock_seed",
            },
        ]
        with self.memory_file.open("a", encoding="utf-8") as handle:
            for record in memory_records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {
            "status": "seeded",
            "records_added": len(memory_records),
            "memory_file": str(self.memory_file),
        }

    def _read_jsonl(self, path: Path, limit: int = 300) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-limit:]
        for line in lines:
            try:
                item = json.loads(line.strip())
                if isinstance(item, dict):
                    records.append(item)
            except json.JSONDecodeError:
                continue
        return records

    @staticmethod
    def _match(item: dict[str, Any], product_key: str, niche_key: str) -> bool:
        if not product_key and not niche_key:
            return True
        product = str(item.get("product_name") or "").lower()
        niche = str(item.get("niche") or item.get("nicho") or "").lower()
        if product_key and product_key in product:
            return True
        if niche_key and niche_key in niche:
            return True
        return False
