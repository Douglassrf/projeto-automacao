"""Missao 88 - Disaster Recovery Validation."""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.services.recovery_service import RecoveryService
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "disaster_recovery_validated"
VERDICT_NOT_READY = "not_ready"


class DisasterRecoveryValidationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.recovery = RecoveryService(db)

    def validation_report(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)

        recovery = self.recovery.recovery_report()
        if not recovery["healthy"] and recovery["recoverable_now"] > 0:
            blocking.append(f"{recovery['recoverable_now']} job(s) recuperavel(is) pendente(s).")
        evidence_extra = recovery
        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": 88,
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "evidence": evidence_extra,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.validation_report()
        lines = ["# Disaster Recovery Validation — Relatorio", "", f"- Veredito: **{report['verdict']}**", f"- Pronto: {report['ready']}", ""]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {issue}")
        return "\n".join(lines)


def get_disaster_recovery_validation_service(db: Session) -> DisasterRecoveryValidationService:
    return DisasterRecoveryValidationService(db=db)

