"""Missao 86 - Production Security Audit."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "security_audit_passed"
VERDICT_NOT_READY = "not_ready"


class ProductionSecurityAuditService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def audit_report(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)

        if self.settings.security_audit_fail_closed is False:
            blocking.append("security_audit_fail_closed=False: gate fail-closed permanentemente fechado.")

        from app.api import safe_router
        sensitive = [r for r in safe_router.LOADED_ROUTES if "secret" in r.lower() or "token" in r.lower()]
        if self.settings.security_audit_fail_closed is False:
            blocking.append("security_audit_fail_closed=False: gate permanentemente fechado.")
        if self.settings.jwt_secret_key == "change-me-super-secret-local-key":
            blocking.append("jwt_secret_key ainda e placeholder de desenvolvimento.")
        evidence_extra = {"loaded_routes": len(safe_router.LOADED_ROUTES), "sensitive_route_hints": len(sensitive)}
        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": 86,
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "evidence": evidence_extra,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.audit_report()
        lines = ["# Production Security Audit — Relatorio", "", f"- Veredito: **{report['verdict']}**", f"- Pronto: {report['ready']}", ""]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {issue}")
        return "\n".join(lines)


def get_production_security_audit_service() -> ProductionSecurityAuditService:
    return ProductionSecurityAuditService()

