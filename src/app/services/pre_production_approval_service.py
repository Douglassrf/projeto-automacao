"""Missao 90 - Pre Production Approval."""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.services.ci_stabilization_service import CiStabilizationService
from app.services.ffmpeg_production_service import FfmpegProductionService
from app.services.test_reliability_service import TestReliabilityService
from app.services.release_candidate_service import ReleaseCandidateService
from app.services.production_security_audit_service import ProductionSecurityAuditService
from app.services.performance_certification_service import PerformanceCertificationService
from app.services.disaster_recovery_validation_service import DisasterRecoveryValidationService
from app.services.documentation_review_service import DocumentationReviewService
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "pre_production_approved"
VERDICT_NOT_READY = "not_ready"


class PreProductionApprovalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self._reports = [
            CiStabilizationService().stabilization_report(),
            FfmpegProductionService().production_report(),
            TestReliabilityService().reliability_report(),
            ReleaseCandidateService().rc1_report(),
            ProductionSecurityAuditService().audit_report(),
            PerformanceCertificationService().performance_report(),
            DisasterRecoveryValidationService(db).validation_report(),
            DocumentationReviewService().review_report(),
        ]

    def approval_report(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)

        if self.settings.pre_production_require_all_missions is False:
            blocking.append("pre_production_require_all_missions=False: gate fail-closed permanentemente fechado.")

        if self.settings.pre_production_require_all_missions:
            for i, r in enumerate(self._reports, start=82):
                if r.get("blocking_issues"):
                    blocking.append(f"M{i}: {r['blocking_issues'][0]}")
        evidence_extra = {"missions_checked": len(self._reports), "verdicts": [r.get("verdict") for r in self._reports]}
        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": 90,
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "evidence": evidence_extra,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.approval_report()
        lines = ["# Pre Production Approval — Relatorio", "", f"- Veredito: **{report['verdict']}**", f"- Pronto: {report['ready']}", ""]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {issue}")
        return "\n".join(lines)


def get_pre_production_approval_service(db: Session) -> PreProductionApprovalService:
    return PreProductionApprovalService(db=db)

