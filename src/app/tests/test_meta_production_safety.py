from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.tests.test_meta_campaign_operator import _payload


def test_meta_operator_returns_payload_preview_for_manual_validation():
    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-operator/v3/launch", json=_payload())
    assert response.status_code == 200
    data = response.json()
    preview = data["payload_preview"]
    assert len(preview["payload_sha256"]) == 64
    assert len(preview["plans"]) == 4
    assert "Revise este JSON" in preview["message"]


def test_meta_operator_blocks_real_publish_without_manual_confirmation():
    settings = get_settings()
    old_autopublish = settings.meta_autopublish
    old_dry_run = settings.meta_dry_run
    old_require = settings.meta_require_manual_confirmation
    old_token = settings.meta_access_token
    old_account = settings.meta_ad_account_id
    old_page = settings.meta_page_id
    try:
        settings.meta_autopublish = True
        settings.meta_dry_run = False
        settings.meta_require_manual_confirmation = True
        settings.meta_access_token = "test-token"
        settings.meta_ad_account_id = "123"
        settings.meta_page_id = "456"
        payload = _payload(mode="publish_paused")
        with TestClient(app) as client:
            response = client.post("/api/v1/campaign-operator/v3/launch", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] == 4
        assert any(item["name"] == "manual_confirmation" and item["status"] == "blocked" for item in data["guardrails"])
    finally:
        settings.meta_autopublish = old_autopublish
        settings.meta_dry_run = old_dry_run
        settings.meta_require_manual_confirmation = old_require
        settings.meta_access_token = old_token
        settings.meta_ad_account_id = old_account
        settings.meta_page_id = old_page


def test_meta_operator_rollback_endpoint_defaults_to_dry_run():
    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-operator/rollback", json={"action": "pause"})
    assert response.status_code == 200
    data = response.json()
    assert data["dry_run"] is True
    assert data["blocked"] is False
