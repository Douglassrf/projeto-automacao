from __future__ import annotations

from dataclasses import dataclass, field
try:
    from enum import StrEnum
except ImportError:  # compat Python 3.10 (StrEnum requer 3.11+)
    from enum import Enum

    class StrEnum(str, Enum):
        pass
from typing import Any

from app.core.security_hardening import (
    SecurityActor,
    SecurityPermission,
    assert_permission,
    service_account,
)


class InternalCallStatus(StrEnum):
    OK = "ok"
    BLOCKED = "blocked"


class ZeroTrustError(RuntimeError):
    pass


@dataclass(frozen=True)
class InternalCall:
    source: SecurityActor
    target_service: str
    permission: SecurityPermission
    scope: str
    correlation_id: str
    execution_id: str = "exec-local-safe"
    mission_id: str = "35D"
    origin: str = "internal"
    payload_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InternalCallValidation:
    status: InternalCallStatus
    blocked_reasons: tuple[str, ...]
    envelope: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status == InternalCallStatus.OK


class ZeroTrustInternalValidator:
    def validate(self, call: InternalCall) -> InternalCallValidation:
        blocked: list[str] = []

        try:
            target = service_account(call.target_service)
        except Exception:
            target = None
            blocked.append("target_service_not_registered")

        try:
            assert_permission(call.source, call.permission)
        except Exception:
            blocked.append("source_permission_denied")

        if not call.correlation_id.strip():
            blocked.append("correlation_id_required")
        elif not self._valid_trace_id(call.correlation_id):
            blocked.append("correlation_id_invalid")

        if not call.execution_id.strip():
            blocked.append("execution_id_required")

        if not call.mission_id.strip():
            blocked.append("mission_id_required")

        if call.scope not in call.source.scopes:
            blocked.append("scope_not_allowed_for_source")

        if target is not None and call.scope not in target.scopes and "audit" not in target.scopes:
            blocked.append("scope_not_allowed_for_target")

        envelope = {
            "source": call.source.actor,
            "source_role": call.source.role.value,
            "target_service": call.target_service,
            "target_role": target.role.value if target else "UNKNOWN",
            "permission": call.permission.value,
            "scope": call.scope,
            "origin": call.origin,
            "correlation_id": call.correlation_id,
            "execution_id": call.execution_id,
            "mission_id": call.mission_id,
            "payload_summary": call.payload_summary,
        }
        status = InternalCallStatus.BLOCKED if blocked else InternalCallStatus.OK
        return InternalCallValidation(status=status, blocked_reasons=tuple(blocked), envelope=envelope)

    def assert_valid(self, call: InternalCall) -> InternalCallValidation:
        result = self.validate(call)
        if not result.ok:
            raise ZeroTrustError(", ".join(result.blocked_reasons))
        return result

    @staticmethod
    def _valid_trace_id(value: str) -> bool:
        normalized = value.strip()
        return normalized.startswith(("REQ-", "corr_", "corr-", "trace_"))


def make_internal_call(
    *,
    source_service: str,
    target_service: str,
    permission: SecurityPermission,
    scope: str,
    correlation_id: str,
    execution_id: str = "exec-local-safe",
    mission_id: str = "35D",
    payload_summary: dict[str, Any] | None = None,
) -> InternalCall:
    return InternalCall(
        source=service_account(source_service),
        target_service=target_service,
        permission=permission,
        scope=scope,
        correlation_id=correlation_id,
        execution_id=execution_id,
        mission_id=mission_id,
        payload_summary=payload_summary or {},
    )

