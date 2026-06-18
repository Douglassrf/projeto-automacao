import pytest

from app.core.immutable_audit import ImmutableAuditLog
from app.core.incident_response import IncidentMode, IncidentResponseMode, IncidentSeverity
from app.core.security_hardening import PermissionDeniedError, SecurityActor, SecurityRole


def test_admin_can_trigger_high_incident_lockdown(tmp_path):
    audit = ImmutableAuditLog(tmp_path / "incident.jsonl")
    incident = IncidentResponseMode(audit_log=audit)
    admin = SecurityActor("Admin", SecurityRole.ADMIN, origin="human")

    report = incident.trigger(
        actor=admin,
        severity=IncidentSeverity.HIGH,
        reason="Meta API retornou comportamento inesperado.",
        evidence={"provider": "meta"},
    )

    runtime = incident.require_safe_runtime()

    assert report.mode == IncidentMode.LOCKDOWN
    assert report.real_execution_blocked is True
    assert report.tokens_should_be_rotated is True
    assert runtime["dry_run_forced"] is True
    assert runtime["real_execution_allowed"] is False
    assert audit.verify().ok is True


def test_medium_incident_forces_dry_run_without_token_rotation():
    incident = IncidentResponseMode()
    admin = SecurityActor("Admin", SecurityRole.ADMIN, origin="human")

    report = incident.trigger(actor=admin, severity=IncidentSeverity.MEDIUM, reason="Erro de modulo isolado.")

    assert report.mode == IncidentMode.DRY_RUN_FORCED
    assert report.tokens_should_be_rotated is False


def test_operator_without_incident_permission_cannot_trigger():
    incident = IncidentResponseMode()
    operator = SecurityActor("Operator", SecurityRole.OPERATOR, origin="human")

    with pytest.raises(PermissionDeniedError):
        incident.trigger(actor=operator, severity=IncidentSeverity.CRITICAL, reason="Tentativa indevida.")


def test_incident_clear_restores_normal_mode(tmp_path):
    audit = ImmutableAuditLog(tmp_path / "incident.jsonl")
    incident = IncidentResponseMode(audit_log=audit)
    admin = SecurityActor("Admin", SecurityRole.ADMIN, origin="human")

    incident.trigger(actor=admin, severity=IncidentSeverity.CRITICAL, reason="Teste.")
    event = incident.clear(admin, notes="Resolvido.")

    runtime = incident.require_safe_runtime()
    assert event["event_type"] == "incident.cleared"
    assert runtime["mode"] == "normal"
    assert runtime["real_execution_allowed"] is True
    assert audit.verify().ok is True
