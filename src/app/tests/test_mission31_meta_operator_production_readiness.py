from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_mission31_production_readiness_blocks_by_default():
    settings = get_settings()
    old = {
        "meta_access_token": settings.meta_access_token,
        "meta_ad_account_id": settings.meta_ad_account_id,
        "meta_page_id": settings.meta_page_id,
    }
    try:
        settings.meta_access_token = None
        settings.meta_ad_account_id = None
        settings.meta_page_id = None
        with TestClient(app) as client:
            response = client.post("/api/v1/campaign-operator/production/readiness", json={"product_name": "Produto Ready"})
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission_id"] == "31"
    assert data["status"] == "blocked"
    assert data["published"] is False
    assert data["would_publish"] is False
    blocked_names = {item["name"] for item in data["blocked_checks"]}
    assert "credentials" in blocked_names
    assert "manual_confirmation" in blocked_names
    assert "rollback_policy" in blocked_names


def test_mission31_production_readiness_can_be_ready_without_publishing():
    settings = get_settings()
    old = {
        "meta_access_token": settings.meta_access_token,
        "meta_ad_account_id": settings.meta_ad_account_id,
        "meta_page_id": settings.meta_page_id,
        "meta_dry_run": settings.meta_dry_run,
        "meta_autopublish": settings.meta_autopublish,
        "meta_operator_enabled": settings.meta_operator_enabled,
    }
    try:
        settings.meta_access_token = "test-token"
        settings.meta_ad_account_id = "123456"
        settings.meta_page_id = "654321"
        settings.meta_dry_run = False
        settings.meta_autopublish = True
        settings.meta_operator_enabled = True
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/campaign-operator/production/readiness",
                json={
                    "product_name": "Produto Ready",
                    "confirmed_by_user": True,
                    "rollback_policy_ack": True,
                    "brain_approval_ack": True,
                    "expected_payload_sha256": "a" * 64,
                },
            )
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ready"
    assert data["published"] is False
    assert data["would_publish"] is True
    assert data["blocked_checks"] == []
    assert data["rollback_required"] is True
    assert data["manual_approval_required"] is True
