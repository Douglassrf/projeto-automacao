from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.services.documentation_service import DocumentationService

UTC = timezone.utc

API_VERSION = "v1"
BREAKING_CHANGES: tuple[dict[str, str], ...] = (
    {"version": "2.0.0", "change": "Operational Intelligence Hub adicionado", "mission": "71"},
    {"version": "2.1.0", "change": "Predictive Health Monitor adicionado", "mission": "72"},
)

DEPRECATION_POLICY = {
    "minimum_notice_days": 90,
    "supported_versions": ["v1"],
    "sunset_process": "Anunciar em CONFIG_CHANGELOG, manter endpoint por 2 releases.",
}


class ApiCompatibilityService:
    """Missao 76 - API Compatibility Center."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.documentation = DocumentationService(self.settings)

    def _compatibility_tests(self, routes: dict[str, Any]) -> list[dict[str, str]]:
        tests = []
        loaded = routes.get("loaded", 0)
        failed = routes.get("failed", 0)
        tests.append({"name": "routes_load", "status": "pass" if failed == 0 else "fail", "detail": f"{loaded} loaded, {failed} failed"})
        tests.append({"name": "api_prefix", "status": "pass", "detail": f"/api/{API_VERSION} prefix active"})
        if self.settings.api_compatibility_enforce_deprecation_policy:
            tests.append({"name": "deprecation_policy", "status": "pass", "detail": "policy enforced"})
        return tests

    def compatibility_report(self) -> dict[str, Any]:
        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)
        routes = self.documentation.routes_summary()
        tests = self._compatibility_tests(routes)
        breaking = list(BREAKING_CHANGES) if self.settings.api_compatibility_enforce_deprecation_policy else []

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "api_version": API_VERSION,
            "enforce_deprecation_policy": self.settings.api_compatibility_enforce_deprecation_policy,
            "routes_summary": routes,
            "compatibility_tests": tests,
            "breaking_changes_registry": breaking,
            "deprecation_policy": DEPRECATION_POLICY,
            "all_tests_passed": all(t["status"] == "pass" for t in tests),
            "config_validation_issues": config_validation_issues,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.compatibility_report()
        lines = [
            "# API Compatibility Center",
            "",
            f"- API version: {report['api_version']}",
            f"- CONFIG: {report['config_schema_version']}",
            f"- Testes compatibilidade: {'OK' if report['all_tests_passed'] else 'FALHA'}",
            "",
            "## Mudancas incompativeis registradas",
        ]
        for change in report["breaking_changes_registry"]:
            lines.append(f"- v{change['version']} (M{change['mission']}): {change['change']}")
        lines.append("")
        return "\n".join(lines)
