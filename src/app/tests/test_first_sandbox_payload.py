from fastapi.testclient import TestClient

from app.core.first_sandbox_payload import first_sandbox_paused_payload
from app.core.sandbox_execution_contract import APPROVAL_PHRASE
from app.main import app


def test_first_sandbox_payload_is_safe_paused_plan_with_approval():
    result = first_sandbox_paused_payload(
        {
            "product_name": "Produto Lead",
            "meta_env": "sandbox",
            "confirmed_by_user": True,
            "approval_phrase": APPROVAL_PHRASE,
        }
    )

    assert result["status"] == "payload_ready_for_manual_sandbox_review"
    assert result["will_execute_real_action"] is False
    assert result["will_activate_spend"] is False
    assert result["can_send_to_meta_api"] is False
    assert result["payload"]["status"] == "PAUSED"
    assert result["payload"]["daily_budget_brl"] == 5
    assert result["payload"]["objective"] == "LEAD"
    assert result["payload"]["safety"]["production_allowed"] is False


def test_first_sandbox_payload_blocks_active_or_over_budget_payload():
    result = first_sandbox_paused_payload(
        {
            "meta_env": "production",
            "campaign_status": "ACTIVE",
            "daily_budget_brl": 20,
        }
    )

    assert result["status"] == "blocked"
    assert "meta_env_must_be_sandbox_or_test_account" in result["blocked_reasons"]
    assert "campaign_must_remain_paused" in result["blocked_reasons"]
    assert "daily_budget_above_sandbox_limit" in result["blocked_reasons"]
    assert "sandbox_human_approval_required" in result["blocked_reasons"]


def test_first_sandbox_payload_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/security/first-sandbox-payload",
            json={"confirmed_by_user": True, "approval_phrase": APPROVAL_PHRASE},
        )

    assert response.status_code == 200
    assert response.json()["payload"]["status"] == "PAUSED"
