from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.real_mode_gate import real_mode_readiness_gate
from app.main import app


def test_real_mode_gate_blocks_without_approval_and_real_meta_setup():
    gate = real_mode_readiness_gate({"target": "meta"})

    assert gate["status"] == "blocked"
    assert "human_approval_required" in gate["blocked_reasons"]
    assert gate["ready_for_assisted_real_mode"] is False


def test_real_mode_gate_can_be_ready_for_sandbox_meta_when_all_safe_flags_are_set():
    settings = get_settings()
    old = {
        "jwt_secret_key": settings.jwt_secret_key,
        "default_admin_password": settings.default_admin_password,
        "meta_access_token": settings.meta_access_token,
        "meta_ad_account_id": settings.meta_ad_account_id,
        "meta_page_id": settings.meta_page_id,
        "meta_dry_run": settings.meta_dry_run,
        "meta_require_manual_confirmation": settings.meta_require_manual_confirmation,
        "meta_allow_active_launch": settings.meta_allow_active_launch,
        "meta_production_daily_spend_limit_brl": settings.meta_production_daily_spend_limit_brl,
        "meta_env": settings.meta_env,
        "meta_allow_production_real": settings.meta_allow_production_real,
        "kill_switch_enabled": settings.kill_switch_enabled,
        "automation_level_2_enabled": settings.automation_level_2_enabled,
    }
    try:
        settings.jwt_secret_key = "rotated-secret-value-for-tests"
        settings.default_admin_password = "rotated-admin-password"
        settings.meta_access_token = "test-token-long-enough"
        settings.meta_ad_account_id = "act_123456"
        settings.meta_page_id = "page_123456"
        settings.meta_dry_run = False
        settings.meta_require_manual_confirmation = True
        settings.meta_allow_active_launch = False
        settings.meta_production_daily_spend_limit_brl = 5
        settings.meta_env = "sandbox"
        settings.meta_allow_production_real = False
        settings.kill_switch_enabled = False
        settings.automation_level_2_enabled = False

        gate = real_mode_readiness_gate(
            {
                "target": "meta",
                "confirmed_by_user": True,
                "approval_phrase": "EU APROVO MODO REAL ASSISTIDO",
            }
        )
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert gate["status"] == "ready"
    assert gate["ready_for_assisted_real_mode"] is True
    assert gate["blocked_reasons"] == []


def test_real_mode_gate_endpoint_reports_policy():
    with TestClient(app) as client:
        response = client.post("/api/v1/security/real-mode-gate", json={"target": "meta"})

    assert response.status_code == 200
    assert response.json()["policy"]["manual_confirmation_required"] is True
