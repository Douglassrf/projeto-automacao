from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.services.documentation_service import DocumentationService

UTC = timezone.utc

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Catalogo estatico de modulos operacionais M41-M72 — metadados descritivos.
MODULE_CATALOG: tuple[dict[str, str], ...] = (
    {"module": "config_profiles", "mission": "41", "service": "config_profiles.py", "doc": "CONFIG_CHANGELOG.md"},
    {"module": "queue", "mission": "42", "service": "queue_service.py", "doc": "M42 report"},
    {"module": "cache", "mission": "43", "service": "cache_service.py", "doc": "M43 report"},
    {"module": "diagnostics", "mission": "44", "service": "diagnostics_service.py", "doc": "M44 report"},
    {"module": "resources", "mission": "45", "service": "resource_manager_service.py", "doc": "M45 report"},
    {"module": "system_alerts", "mission": "46", "service": "alert_service.py", "doc": "M46 report"},
    {"module": "recovery", "mission": "47", "service": "recovery_service.py", "doc": "M47 report"},
    {"module": "documentation", "mission": "48", "service": "documentation_service.py", "doc": "M48 report"},
    {"module": "dependency_audit", "mission": "49", "service": "dependency_audit_service.py", "doc": "M49 report"},
    {"module": "certification", "mission": "50", "service": "certification_service.py", "doc": "M50 report"},
    {"module": "operational_intelligence", "mission": "71", "service": "operational_intelligence_service.py", "doc": "M71 report"},
    {"module": "predictive_health", "mission": "72", "service": "predictive_health_service.py", "doc": "M72 report"},
)

ARCHITECTURAL_DECISIONS: tuple[dict[str, str], ...] = (
    {
        "id": "ADR-001",
        "title": "Config centralizada com validate_settings fail-closed",
        "mission": "41",
        "status": "accepted",
        "summary": "CONFIG_SCHEMA_VERSION versionado separadamente do app VERSION.",
    },
    {
        "id": "ADR-002",
        "title": "Certificacao Platinum agrega servicos sem reimplementar",
        "mission": "50",
        "status": "accepted",
        "summary": "Capstone M41-M49 usa apenas leitura dos servicos existentes.",
    },
    {
        "id": "ADR-003",
        "title": "Operational Intelligence Hub como painel unificado",
        "mission": "71",
        "status": "accepted",
        "summary": "Quatro eixos: global_project_state, stability, performance, risk.",
    },
)

LESSONS_LEARNED: tuple[dict[str, str], ...] = (
    {
        "id": "LL-001",
        "topic": "Reuso vs reimplementacao",
        "lesson": "Missoes operacionais devem compor servicos existentes, nunca duplicar logica.",
        "source_mission": "50",
    },
    {
        "id": "LL-002",
        "topic": "Gates fail-closed",
        "lesson": "Flags bool de gate desligadas em producao devem ser rejeitadas por validate_settings.",
        "source_mission": "41",
    },
    {
        "id": "LL-003",
        "topic": "Documentacao viva",
        "lesson": "Snapshots gerados em runtime evitam docs estaticos desatualizados.",
        "source_mission": "48",
    },
)


class TechnicalKnowledgeService:
    """Missao 73 - Technical Knowledge Base.

    Catalogo de modulos, historico de decisoes arquiteturais (ADRs),
    licoes aprendidas e referencias cruzadas doc↔codigo. Reutiliza
    DocumentationService (M48) para rotas e config em tempo real.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.documentation = DocumentationService(self.settings)

    def _cross_references(self) -> list[dict[str, str]]:
        refs: list[dict[str, str]] = []
        for entry in MODULE_CATALOG:
            service_path = f"src/app/services/{entry['service']}"
            route_path = f"src/app/api/routes/{entry['module']}.py"
            refs.append(
                {
                    "module": entry["module"],
                    "mission": entry["mission"],
                    "code_service": service_path,
                    "code_route": route_path if ( _PROJECT_ROOT / route_path ).exists() else "N/A",
                    "documentation": entry["doc"],
                }
            )
        changelog = _PROJECT_ROOT / "CONFIG_CHANGELOG.md"
        if changelog.exists():
            refs.append(
                {
                    "module": "config",
                    "mission": "41",
                    "code_service": "src/app/core/config_profiles.py",
                    "code_route": "src/app/core/config.py",
                    "documentation": "CONFIG_CHANGELOG.md",
                }
            )
        return refs

    def _filtered_catalog(self, routes_summary: dict[str, Any]) -> list[dict[str, str]]:
        loaded_names = {
            item.rsplit(".", 1)[-1] for item in routes_summary.get("loaded_modules", [])
        }
        catalog: list[dict[str, str]] = []
        for entry in MODULE_CATALOG:
            if not self.settings.technical_knowledge_include_draft_modules:
                route_module = f"app.api.routes.{entry['module']}"
                if route_module not in routes_summary.get("loaded_modules", []):
                    continue
            catalog.append({**entry, "route_loaded": str(entry["module"] in loaded_names or f"routes.{entry['module']}" in str(loaded_names))})
        return catalog

    def knowledge_base(self) -> dict[str, Any]:
        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)
        routes = self.documentation.routes_summary()
        doc_snapshot = self.documentation.live_snapshot()

        adrs = list(ARCHITECTURAL_DECISIONS)
        if not self.settings.technical_knowledge_include_draft_adrs:
            adrs = [a for a in adrs if a.get("status") == "accepted"]

        cross_refs = self._cross_references()
        if not self.settings.technical_knowledge_include_cross_references:
            cross_refs = []

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "include_draft_adrs": self.settings.technical_knowledge_include_draft_adrs,
            "include_draft_modules": self.settings.technical_knowledge_include_draft_modules,
            "module_catalog": self._filtered_catalog(routes),
            "module_catalog_total": len(MODULE_CATALOG),
            "architectural_decisions": adrs,
            "lessons_learned": list(LESSONS_LEARNED),
            "cross_references": cross_refs,
            "routes_summary": routes,
            "documentation_field_count": doc_snapshot["settings_field_count"],
            "config_validation_issues": config_validation_issues,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.knowledge_base()
        lines: list[str] = []
        lines.append("# Technical Knowledge Base")
        lines.append("")
        lines.append(f"- Gerado em: {report['generated_at']}")
        lines.append(f"- Ambiente: {report['environment']}")
        lines.append(f"- Modulos catalogados: {len(report['module_catalog'])}/{report['module_catalog_total']}")
        lines.append("")

        lines.append("## Catalogo de modulos")
        lines.append("")
        for mod in report["module_catalog"]:
            lines.append(f"- M{mod['mission']} `{mod['module']}` → `{mod['service']}`")
        lines.append("")

        lines.append("## Decisoes arquiteturais")
        lines.append("")
        for adr in report["architectural_decisions"]:
            lines.append(f"- **{adr['id']}** ({adr['status']}): {adr['title']}")
        lines.append("")

        lines.append("## Licoes aprendidas")
        lines.append("")
        for lesson in report["lessons_learned"]:
            lines.append(f"- {lesson['id']}: {lesson['lesson']}")
        lines.append("")

        lines.append("## Referencias cruzadas doc↔codigo")
        lines.append("")
        for ref in report["cross_references"]:
            lines.append(
                f"- M{ref['mission']} `{ref['module']}`: {ref['code_service']} ↔ {ref['documentation']}"
            )
        lines.append("")

        return "\n".join(lines)
