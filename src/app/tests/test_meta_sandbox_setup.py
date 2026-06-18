from fastapi.testclient import TestClient

from app.core.meta_sandbox_setup import meta_sandbox_setup_check
from app.main import app


def test_meta_sandbox_setup_check_blocks_production_or_active_status():
    result = meta_sandbox_setup_check({"meta_env": "production", "campaign_status": "ACTIVE", "daily_budget_brl": 20})

    assert result["status"] == "blocked"
    assert result["will_execute_real_action"] is False
    assert result["will_activate_spend"] is False
    assert "meta_env_not_sandbox_or_test_account" in result["blocked_reasons"]
    assert "campaign_not_paused" in result["blocked_reasons"]
    assert "sandbox_budget_above_5_brl" in result["blocked_reasons"]


def test_meta_sandbox_setup_check_allows_safe_manual_configuration_shape():
    result = meta_sandbox_setup_check({"meta_env": "sandbox", "campaign_status": "PAUSED", "daily_budget_brl": 5})

    assert result["status"] == "ready_for_manual_sandbox_configuration"
    assert result["safe_payload_defaults"]["objective"] == "LEAD"
    assert "confirmar Business/Profile empresarial na Meta" in result["manual_setup_steps"]


def test_meta_sandbox_setup_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/security/meta-sandbox-setup", json={"meta_env": "sandbox"})

    assert response.status_code == 200
    assert response.json()["safe_payload_defaults"]["campaign_status"] == "PAUSED"
