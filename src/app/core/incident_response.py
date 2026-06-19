from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
try:
    from enum import StrEnum
except ImportError:  # compat Python 3.10 (StrEnum requer 3.11+)
    from enum import Enum

    class StrEnum(str, Enum):
        pass
from typing import Any

from app.core.human_approval import ApprovalStatus
from app.core.immutable_audit import ImmutableAuditLog
from app.core.security_hardening import SecurityActor, SecurityPermission, assert_permission


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentMode(StrEnum):
    NORMAL = "normal"
    DRY_RUN_FORCED = "dry_run_forced"
    LOCKDOWN = "lockdown"


class IncidentResponseError(RuntimeError):
    pass


@dataclass(frozen=True)
class IncidentReport:
    incident_id: str
    severity: IncidentSeverity
    mode: IncidentMode
    triggered_by: str
    reason: str
    real_execution_blocked: bool
    dry_run_forced: bool
    tokens_should_be_rotated: bool
    approvals_status: ApprovalStatus
    created_at: str
    actions: tuple[str, ...]
    evidence: dict[str, Any] = field(default_factory=dict)


class IncidentResponseMode:
    def __init__(self, audit_log: ImmutableAuditLog | None = None) -> None:
        self.audit_log = audit_log
        self.current_mode = IncidentMode.NORMAL
        self.last_report: IncidentReport | None = None

    def trigger(
        self,
        *,
        actor: SecurityActor,
        severity: IncidentSeverity,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> IncidentReport:
        assert_permission(actor, SecurityPermission.INCIDENT_MANAGE)
        mode = IncidentMode.LOCKDOWN if severity in {IncidentSeverity.HIGH, IncidentSeverity.CRITICAL} else IncidentMode.DRY_RUN_FORCED
        report = IncidentReport(
            incident_id=self._incident_id(actor.actor, reason),
            severity=severity,
            mode=mode,
            triggered_by=actor.actor,
            reason=reason,
            real_execution_blocked=True,
            dry_run_forced=True,
            tokens_should_be_rotated=severity in {IncidentSeverity.HIGH, IncidentSeverity.CRITICAL},
            approvals_status=ApprovalStatus.INCIDENT,
            created_at=datetime.now(UTC).isoformat(),
            actions=(
                "force_dry_run",
                "block_real_execution",
                "preserve_logs",
                "notify_admin",
                "review_tokens",
            ),
            evidence=evidence or {},
        )
        self.current_mode = report.mode
        self.last_report = report
        self._audit("incident.triggered", report)
        return report

    def require_safe_runtime(self) -> dict[str, Any]:
        report = self.last_report
        return {
            "mode": self.current_mode.value,
            "dry_run_forced": self.current_mode != IncidentMode.NORMAL,
            "real_execution_allowed": self.current_mode == IncidentMode.NORMAL,
            "incident_id": report.incident_id if report else "",
        }

    def clear(self, actor: SecurityActor, notes: str = "") -> dict[str, Any]:
        assert_permission(actor, SecurityPermission.INCIDENT_MANAGE)
        previous = self.last_report.incident_id if self.last_report else ""
        self.current_mode = IncidentMode.NORMAL
        self.last_report = None
        event = {
            "event_type": "incident.cleared",
            "cleared_by": actor.actor,
            "previous_incident_id": previous,
            "notes": notes,
            "created_at": datetime.now(UTC).isoformat(),
        }
        if self.audit_log:
            self.audit_log.append(event)
        return event

    def _audit(self, event_type: str, report: IncidentReport) -> None:
        if self.audit_log is None:
            return
        self.audit_log.append({"event_type": event_type, **report.__dict__, "severity": report.severity.value, "mode": report.mode.value, "approvals_status": report.approvals_status.value})

    @staticmethod
    def _incident_id(actor: str, reason: str) -> str:
        seed = f"{actor}:{reason}:{datetime.now(UTC).isoformat()}"
        import hashlib

        return f"inc_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"

