from __future__ import annotations

import hashlib
import json
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

from app.core.immutable_audit import ImmutableAuditLog
from app.core.security_hardening import SecurityActor, SecurityPermission, assert_permission


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"
    AUDITED = "audited"
    INCIDENT = "incident"


class ApprovalError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovalRequest:
    action: str
    resource_type: str
    requested_by: SecurityActor
    payload: dict[str, Any]
    correlation_id: str
    resource_id: str | None = None
    reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def payload_hash(self) -> str:
        canonical = json.dumps(self.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def approval_id(self) -> str:
        raw = f"{self.action}:{self.resource_type}:{self.resource_id or ''}:{self.payload_hash}:{self.correlation_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    status: ApprovalStatus
    action: str
    resource_type: str
    resource_id: str | None
    requested_by: str
    decided_by: str = ""
    payload_hash: str = ""
    correlation_id: str = ""
    reason: str = ""
    notes: str = ""
    created_at: str = ""
    decided_at: str = ""


class HumanApprovalLayer:
    def __init__(self, audit_log: ImmutableAuditLog | None = None) -> None:
        self._records: dict[str, ApprovalRecord] = {}
        self.audit_log = audit_log

    def request(self, approval: ApprovalRequest) -> ApprovalRecord:
        assert_permission(approval.requested_by, SecurityPermission.APPROVAL_CREATE)
        record = ApprovalRecord(
            approval_id=approval.approval_id,
            status=ApprovalStatus.PENDING,
            action=approval.action,
            resource_type=approval.resource_type,
            resource_id=approval.resource_id,
            requested_by=approval.requested_by.actor,
            payload_hash=approval.payload_hash,
            correlation_id=approval.correlation_id,
            reason=approval.reason,
            created_at=approval.created_at,
        )
        self._records[record.approval_id] = record
        self._audit("approval.requested", record)
        return record

    def approve(self, approval_id: str, actor: SecurityActor, notes: str = "") -> ApprovalRecord:
        return self._decide(approval_id, actor, ApprovalStatus.APPROVED, notes)

    def reject(self, approval_id: str, actor: SecurityActor, notes: str = "") -> ApprovalRecord:
        return self._decide(approval_id, actor, ApprovalStatus.REJECTED, notes)

    def mark_executed(self, approval_id: str, actor: SecurityActor, notes: str = "") -> ApprovalRecord:
        record = self._get(approval_id)
        if record.status != ApprovalStatus.APPROVED:
            raise ApprovalError(f"Aprovacao precisa estar approved antes de executed; status atual: {record.status}.")
        updated = self._replace(record, status=ApprovalStatus.EXECUTED, decided_by=actor.actor, notes=notes)
        self._audit("approval.executed", updated)
        return updated

    def get(self, approval_id: str) -> ApprovalRecord:
        return self._get(approval_id)

    def _decide(self, approval_id: str, actor: SecurityActor, status: ApprovalStatus, notes: str) -> ApprovalRecord:
        assert_permission(actor, SecurityPermission.APPROVAL_DECIDE)
        record = self._get(approval_id)
        if record.status != ApprovalStatus.PENDING:
            raise ApprovalError(f"Aprovacao nao esta pending; status atual: {record.status}.")
        updated = self._replace(record, status=status, decided_by=actor.actor, notes=notes)
        self._audit(f"approval.{status.value}", updated)
        return updated

    def _get(self, approval_id: str) -> ApprovalRecord:
        try:
            return self._records[approval_id]
        except KeyError as exc:
            raise ApprovalError(f"Aprovacao nao encontrada: {approval_id}") from exc

    def _replace(self, record: ApprovalRecord, **changes: Any) -> ApprovalRecord:
        data = record.__dict__ | {"decided_at": datetime.now(UTC).isoformat()} | changes
        updated = ApprovalRecord(**data)
        self._records[record.approval_id] = updated
        return updated

    def _audit(self, event_type: str, record: ApprovalRecord) -> None:
        if self.audit_log is None:
            return
        self.audit_log.append(
            {
                "event_type": event_type,
                "approval_id": record.approval_id,
                "status": record.status.value,
                "action": record.action,
                "resource_type": record.resource_type,
                "resource_id": record.resource_id,
                "requested_by": record.requested_by,
                "decided_by": record.decided_by,
                "payload_hash": record.payload_hash,
                "correlation_id": record.correlation_id,
            }
        )

