from fastapi.testclient import TestClient

from app.core.sandbox_execution_contract import APPROVAL_PHRASE, sandbox_execution_contract
from app.main import app


def test_sandbox_execution_contract_blocks_active_or_unapproved_request():
    contract = sandbox_execution_contract(
        {
            "meta_env": "production",
            "daily_budget_brl": 50,
            "campaign_status": "ACTIVE",
            "allow_active_launch": True,
        }
    )

    assert contract["status"] == "blocked"
    assert contract["will_execute_real_action"] is False
    assert contract["will_activate_spend"] is False
    assert "meta_env_must_be_sandbox_or_test_account" in contract["blocked_reasons"]
    assert "active_launch_forbidden" in contract["blocked_reasons"]


def test_sandbox_execution_contract_allows_only_paused_low_budget_sandbox_preparation():
    contract = sandbox_execution_contract(
        {
            "meta_env": "sandbox",
            "daily_budget_brl": 5,
            "campaign_status": "PAUSED",
            "confirmed_by_user": True,
            "approval_phrase": APPROVAL_PHRASE,
        }
    )

    assert contract["status"] == "contract_valid"
    assert contract["can_prepare_sandbox_execution"] is True
    assert contract["will_execute_real_action"] is False
    assert contract["contract"]["max_daily_budget_brl"] == 5


def test_sandbox_execution_contract_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/security/sandbox-execution-contract", json={})

    assert response.status_code == 200
    assert response.json()["production_ready"] is False
