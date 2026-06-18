from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


class KnowledgeEngineError(RuntimeError):
    pass


class KnowledgeEngine:
    """Carrega o Marketing Knowledge Core a partir de /server/knowledge.

    A leitura acontece em tempo de execução. Assim, regras, thresholds, GEOs e
    estratégias V1/V2/V3 podem ser ajustadas em JSON sem alterar o código da app.
    """

    def __init__(self, knowledge_dir: Path | None = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).resolve().parents[2] / "knowledge"
        self.knowledge_dir = knowledge_dir.resolve()

    def load(self, name: str) -> dict[str, Any]:
        safe_name = name.replace("/", "").replace("..", "")
        path = self.knowledge_dir / f"{safe_name}.json"
        if not path.exists():
            raise KnowledgeEngineError(f"Knowledge file not found: {safe_name}.json")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KnowledgeEngineError(f"Invalid JSON in {safe_name}.json: {exc}") from exc

    def load_all(self) -> dict[str, dict[str, Any]]:
        if not self.knowledge_dir.exists():
            raise KnowledgeEngineError(f"Knowledge directory not found: {self.knowledge_dir}")
        data: dict[str, dict[str, Any]] = {}
        for path in sorted(self.knowledge_dir.glob("*.json")):
            data[path.stem] = self.load(path.stem)
        return data

    def marketing_context(self) -> dict[str, Any]:
        return {
            "v1": self.load("v1_strategy"),
            "v2": self.load("v2_strategy"),
            "v3": self.load("v3_strategy"),
            "geo": self.load("geo_rules"),
            "pixel": self.load("pixel_rules"),
            "metrics": self.load("metrics_rules"),
            "copy_patterns": self.load("copy_patterns"),
            "creative_patterns": self.load("creative_patterns"),
            "scaling": self.load("scaling_rules"),
            "learning_loop": self.load("learning_loop_rules"),
        }

    def campaign_models(self) -> dict[str, str]:
        ctx = self.marketing_context()
        return {
            "V1": ctx["v1"].get("name", "V1"),
            "V2": ctx["v2"].get("name", "V2"),
            "V3": ctx["v3"].get("name", "V3"),
        }

    def guardrails(self) -> list[str]:
        pixel_rules = self.load("pixel_rules").get("rules", [])
        creative_rules = self.load("creative_patterns").get("rules", [])
        metrics_rules = self.load("metrics_rules").get("analysis_rules", [])
        return [*pixel_rules, *creative_rules, *metrics_rules]

    def geo_preset(self, preset: str) -> dict[str, Any] | None:
        return self.load("geo_rules").get("presets", {}).get(preset)

    def connect_rate_warning_below(self) -> float:
        return float(self.load("metrics_rules").get("connect_rate", {}).get("warning_below", 75))


@lru_cache(maxsize=1)
def get_knowledge_engine() -> KnowledgeEngine:
    return KnowledgeEngine()
