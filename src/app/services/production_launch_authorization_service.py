"""Missao 91 - Production Launch Authorization."""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.services.pre_production_approval_service import PreProductionApprovalService
from app.services.integration_control_service import get_integration_control_service
from app.services.autonomous_operations_service import AutonomousOperationsService
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "production_launch_authorized"
VERDICT_NOT_READY = "not_ready"


class ProductionLaunchAuthorizationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.pre = PreProductionApprovalService(db)
        self.integration = get_integration_control_service()
        self.autonomous = AutonomousOperationsService(db)

    def authorization_report(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)

        if self.settings.production_launch_fail_closed is False:
            blocking.append("production_launch_fail_closed=False: gate fail-closed permanentemente fechado.")

        if self.settings.production_launch_fail_closed is False:
            blocking.append("production_launch_fail_closed=False: gate permanentemente fechado.")
        pre = self.pre.approval_report()
        integration = self.integration.merge_health_report()
        autonomous = self.autonomous.readiness_report()
        for label, rep in [("pre", pre), ("integration", integration), ("autonomous", autonomous)]:
            if rep.get("blocking_issues"):
                blocking.append(f"{label}: {rep['blocking_issues'][0]}")
        evidence_extra = {
            "pre_verdict": pre.get("verdict"),
            "integration_verdict": integration.get("verdict"),
            "autonomous_verdict": autonomous.get("verdict"),
            "evidence_archive": "RELATORIO_FASE_V17_M82_M91.md",
        }
        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": 91,
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "evidence": evidence_extra,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.authorization_report()
        lines = ["# Production Launch Authorization — Relatorio", "", f"- Veredito: **{report['verdict']}**", f"- Pronto: {report['ready']}", ""]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {issue}")
        return "\n".join(lines)


def get_production_launch_authorization_service(db: Session) -> ProductionLaunchAuthorizationService:
    return ProductionLaunchAuthorizationService(db=db)

