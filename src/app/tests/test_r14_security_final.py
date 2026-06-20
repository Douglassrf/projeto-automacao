from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.meta_sandbox_setup import meta_sandbox_setup_check
from app.core.real_mode_gate import real_mode_readiness_gate
from app.core.security import create_access_token, decode_access_token
from app.core.security_hardening import SecurityPermission, SecurityRole, roles_matrix
from app.main import app
from app.services.observability import immutable_audit_event, immutable_audit_health


def test_r14_rbac_matrix_exists_and_blocks_privileged_meta_permissions():
    matrix = roles_matrix()

    assert set(matrix) == {role.value for role in SecurityRole}
    assert SecurityPermission.META_REAL_EXECUTE.value in matrix[SecurityRole.OWNER.value]
    assert SecurityPermission.META_REAL_EXECUTE.value not in matrix[SecurityRole.OPERATOR.value]
    assert SecurityPermission.META_DRY_RUN.value in matrix[SecurityRole.OPERATOR.value]
    assert SecurityPermission.META_DRY_RUN.value in matrix[SecurityRole.SERVICE.value]


def test_r14_auth_required_default_and_jwt_roundtrip_are_validated():
    default_settings = Settings()
    runtime_settings = get_settings()

    assert default_settings.auth_required is True
    assert runtime_settings.auth_required in {True, False}

    previous_secret = runtime_settings.jwt_secret_key
    try:
        runtime_settings.jwt_secret_key = "rotated-r14-test-secret-placeholder"
        token = create_access_token("r14-user", extra={"email": "r14@example.com"})
        payload = decode_access_token(token)
    finally:
        runtime_settings.jwt_secret_key = previous_secret

    assert payload["sub"] == "r14-user"
    assert payload["email"] == "r14@example.com"
    assert "exp" in payload


def test_r14_cors_middleware_remains_absent_and_no_cors_headers_are_emitted():
    assert not any(middleware.cls is CORSMiddleware for middleware in app.user_middleware)

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://example.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert "access-control-allow-origin" not in {key.lower() for key in response.headers}


def test_r14_immutable_audit_chain_remains_valid_after_security_blocks():
    before = immutable_audit_health()
    assert before["hash_chain_ok"] is True

    blocked = immutable_audit_event(
        actor="R14SecurityFinal",
        action="security.final.blocked_check",
        resource_type="security_final",
        resource_id="R14",
        status="blocked",
        details={"source": "r14_final_security_test", "no_secret": True},
        mission_id="R14",
        correlation_id="REQ-R14-SECURITY-FINAL",
        execution_id="exec-r14-security-final",
    )
    after = immutable_audit_health()

    assert len(blocked["event_hash"]) == 64
    assert after["hash_chain_ok"] is True
    assert after["total_events"] >= before["total_events"] + 1
    assert after["broken_at"] is None


def test_r14_meta_flags_remain_safe_and_real_mode_gate_blocks_by_default():
    settings = get_settings()

    assert settings.meta_dry_run is True
    assert settings.meta_allow_active_launch is False
    assert settings.meta_autopublish is False
    assert settings.meta_allow_production_real is False

    gate = real_mode_readiness_gate({"target": "meta"})
    assert gate["status"] == "blocked"
    assert gate["ready_for_assisted_real_mode"] is False
    assert "human_approval_required" in gate["blocked_reasons"]
    assert "meta_dry_run_enabled" in gate["blocked_reasons"]

    sandbox = meta_sandbox_setup_check({"daily_budget_brl": 5, "campaign_status": "PAUSED"})
    assert sandbox["will_execute_real_action"] is False
    assert sandbox["will_activate_spend"] is False
