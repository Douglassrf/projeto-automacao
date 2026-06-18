from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_rollback_formal_policy_defaults_to_dry_run_ready_without_execution():
    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-operator/rollback/policy", json={"product_name": "Produto Rollback"})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission_id"] == "rollback-formal"
    assert data["status"] == "dry_run_ready"
    assert data["executed"] is False
    assert data["would_execute_real_rollback"] is False
    assert data["manual_approval_required"] is True
    assert data["rollback_endpoint"] == "/api/v1/campaign-operator/rollback"


def test_rollback_formal_policy_blocks_real_request_without_required_approvals():
    settings = get_settings()
    old = {
        "meta_autopublish": settings.meta_autopublish,
        "meta_access_token": settings.meta_access_token,
        "meta_ad_account_id": settings.meta_ad_account_id,
        "meta_page_id": settings.meta_page_id,
    }
    try:
        settings.meta_autopublish = False
        settings.meta_access_token = None
        settings.meta_ad_account_id = None
        settings.meta_page_id = None
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/campaign-operator/rollback/policy",
                json={"product_name": "Produto Rollback", "force_dry_run": False},
            )
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "blocked"
    assert data["executed"] is False
    assert data["would_execute_real_rollback"] is False
    blocked_names = {item["name"] for item in data["blocked_checks"]}
    assert "manual_confirmation" in blocked_names
    assert "rollback_policy_ack" in blocked_names
    assert "brain_approval" in blocked_names
    assert "operator_autopublish" in blocked_names
    assert "credentials" in blocked_names
