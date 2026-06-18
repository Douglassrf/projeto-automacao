import pytest

from app.core.security_hardening import (
    PermissionDeniedError,
    SecurityActor,
    SecurityPermission,
    SecurityRole,
    assert_permission,
    can,
    roles_matrix,
    service_account,
)


def test_agent_service_account_can_create_decision_but_cannot_execute_meta_real():
    brain = service_account("CampaignBrain")

    assert brain.role == SecurityRole.AGENT
    assert can(brain, SecurityPermission.DECISION_CREATE)
    assert can(brain, SecurityPermission.META_DRY_RUN)
    assert not can(brain, SecurityPermission.META_REAL_EXECUTE)


def test_operator_can_request_real_meta_but_cannot_execute_without_owner_layer():
    operator = SecurityActor("DouglasOperator", SecurityRole.OPERATOR, origin="human")

    assert can(operator, SecurityPermission.META_REAL_REQUEST)
    assert not can(operator, SecurityPermission.META_REAL_EXECUTE)


def test_owner_has_all_permissions_and_viewer_is_read_only():
    owner = SecurityActor("Douglas", SecurityRole.OWNER, origin="human")
    viewer = SecurityActor("ReadOnly", SecurityRole.VIEWER, origin="human")

    assert can(owner, SecurityPermission.INCIDENT_MANAGE)
    assert can(owner, SecurityPermission.META_REAL_EXECUTE)
    assert can(viewer, SecurityPermission.AUDIT_READ)
    assert not can(viewer, SecurityPermission.APPROVAL_DECIDE)


def test_unknown_service_account_is_blocked():
    with pytest.raises(PermissionDeniedError):
        service_account("UnknownAgent")


def test_zero_trust_context_contains_required_fields():
    brian = service_account("Brian")
    context = brian.context(
        permission=SecurityPermission.DECISION_CREATE,
        correlation_id="REQ-2026-0001",
        scope="decision",
    )

    assert context == {
        "actor": "Brian",
        "role": "AGENT",
        "permission": "decision.create",
        "correlation_id": "REQ-2026-0001",
        "origin": "internal",
        "scope": "decision",
    }


def test_assert_permission_blocks_forbidden_action():
    meta_operator = service_account("MetaCampaignOperator")

    with pytest.raises(PermissionDeniedError):
        assert_permission(meta_operator, SecurityPermission.META_REAL_EXECUTE)


def test_roles_matrix_exposes_all_official_roles():
    matrix = roles_matrix()

    assert set(matrix) == {"OWNER", "ADMIN", "OPERATOR", "VIEWER", "AGENT", "SERVICE"}
    assert "meta.real.execute" in matrix["OWNER"]
    assert "meta.real.execute" not in matrix["AGENT"]
