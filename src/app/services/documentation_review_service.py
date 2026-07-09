"""Missao 89 - Final Documentation Review."""
from __future__ import annotations
from app.services.documentation_service import DocumentationService
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "documentation_review_passed"
VERDICT_NOT_READY = "not_ready"


class DocumentationReviewService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def review_report(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)

        if self.settings.documentation_review_require_complete is False:
            blocking.append("documentation_review_require_complete=False: gate fail-closed permanentemente fechado.")

        doc = DocumentationService().live_snapshot()
        loaded = doc.get("routes", {}).get("loaded", 0)
        if self.settings.documentation_review_require_complete and loaded < 1:
            blocking.append("Documentacao viva nao reporta rotas carregadas.")
        evidence_extra = {"routes_loaded": loaded, "config_fields": doc.get("settings_field_count", 0)}
        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": 89,
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "evidence": evidence_extra,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.review_report()
        lines = ["# Final Documentation Review — Relatorio", "", f"- Veredito: **{report['verdict']}**", f"- Pronto: {report['ready']}", ""]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {issue}")
        return "\n".join(lines)


def get_documentation_review_service() -> DocumentationReviewService:
    return DocumentationReviewService()

