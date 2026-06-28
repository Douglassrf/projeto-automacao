from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.services.documentation_service import DocumentationService, _read_version_file

UTC = timezone.utc
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

VERSION_MILESTONES: tuple[dict[str, str], ...] = (
    {"config_version": "1.9.0", "mission": "50", "label": "Certificacao Platinum"},
    {"config_version": "2.0.0", "mission": "71", "label": "Operational Intelligence Hub"},
    {"config_version": "2.7.0", "mission": "78", "label": "Resource Optimization Engine"},
    {"config_version": "2.8.0", "mission": "79", "label": "Architecture Evolution Report"},
)


class ArchitectureEvolutionService:
    """Missao 79 - Architecture Evolution Report."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.documentation = DocumentationService(self.settings)

    def _complexity_indicators(self, routes: dict[str, Any], settings_count: int) -> dict[str, Any]:
        loaded = routes.get("loaded", 0)
        failed = routes.get("failed", 0)
        score = loaded * 2 + settings_count * 0.5 + failed * 10
        return {
            "routes_loaded": loaded,
            "routes_failed": failed,
            "settings_field_count": settings_count,
            "complexity_score": round(score, 1),
            "complexity_level": "high" if score > 200 else "medium" if score > 100 else "low",
        }

    def _refactoring_areas(self, routes: dict[str, Any]) -> list[str]:
        areas: list[str] = []
        if routes.get("failed", 0) > 0:
            areas.append("Rotas com falha de carregamento requerem investigacao")
        if self.settings.architecture_evolution_include_recommendations:
            areas.append("Considerar pin de dependencias (19/19 unpinned)")
            areas.append("Consolidar rotas *_safe duplicadas onde possivel")
        return areas

    def _recommendations(self, complexity: dict[str, Any]) -> list[str]:
        if not self.settings.architecture_evolution_include_recommendations:
            return []
        recs = [
            "Manter CONFIG_CHANGELOG atualizado a cada missao",
            "Executar certificacao Platinum antes de releases",
        ]
        if complexity["complexity_level"] == "high":
            recs.append("Complexidade alta: priorizar modularizacao de servicos")
        return recs

    def evolution_report(self) -> dict[str, Any]:
        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)
        doc = self.documentation.live_snapshot()
        routes = doc["routes"]
        complexity = self._complexity_indicators(routes, doc["settings_field_count"])

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "app_version": _read_version_file(),
            "include_recommendations": self.settings.architecture_evolution_include_recommendations,
            "version_milestones": list(VERSION_MILESTONES),
            "current_vs_previous": {
                "current_config": CONFIG_SCHEMA_VERSION,
                "previous_milestone": "2.7.0",
                "missions_since_m71": 8,
            },
            "complexity_indicators": complexity,
            "refactoring_areas": self._refactoring_areas(routes),
            "technical_recommendations": self._recommendations(complexity),
            "config_validation_issues": config_validation_issues,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.evolution_report()
        c = report["complexity_indicators"]
        lines = [
            "# Architecture Evolution Report",
            "",
            f"- CONFIG: {report['config_schema_version']}",
            f"- Complexidade: {c['complexity_level']} (score {c['complexity_score']})",
            "",
            "## Areas de refatoracao",
        ]
        for area in report["refactoring_areas"]:
            lines.append(f"- {area}")
        lines.append("")
        lines.append("## Recomendacoes")
        for rec in report["technical_recommendations"]:
            lines.append(f"- {rec}")
        return "\n".join(lines)
