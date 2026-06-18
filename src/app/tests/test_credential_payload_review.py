import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.tests.test_meta_campaign_operator import _payload


def test_credential_payload_review_blocks_by_default_and_redacts_secrets():
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
            response = client.post(
                "/api/v1/campaign-operator/production/credential-review",
                json={"launch_payload": _payload(mode="publish_paused")},
            )
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission_id"] == "credential-payload-review"
    assert data["status"] == "blocked"
    assert data["published"] is False
    assert data["secrets_redacted"] is True
    blocked_names = {item["name"] for item in data["blocked_checks"]}
    assert "access_token_present" in blocked_names
    assert "manual_confirmation" in blocked_names


def test_credential_payload_review_can_be_ready_without_exposing_token_or_publishing():
    settings = get_settings()
    old = {
        "meta_access_token": settings.meta_access_token,
        "meta_ad_account_id": settings.meta_ad_account_id,
        "meta_page_id": settings.meta_page_id,
        "meta_dry_run": settings.meta_dry_run,
        "meta_autopublish": settings.meta_autopublish,
    }
    try:
        settings.meta_access_token = "test-token-secret"
        settings.meta_ad_account_id = "123456"
        settings.meta_page_id = "654321"
        settings.meta_dry_run = False
        settings.meta_autopublish = True
        payload = {
            "launch_payload": _payload(mode="publish_paused"),
            "confirmed_by_user": True,
            "rollback_policy_ack": True,
            "brain_approval_ack": True,
        }
        with TestClient(app) as client:
            first = client.post("/api/v1/campaign-operator/production/credential-review", json=payload)
            payload["expected_payload_sha256"] = first.json()["payload_preview"]["payload_sha256"]
            response = client.post("/api/v1/campaign-operator/production/credential-review", json=payload)
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ready"
    assert data["published"] is False
    assert data["would_publish"] is True
    assert data["payload_preview"]["campaign_count"] == 4
    assert data["credentials"]["access_token_present"] is True
    assert "test-token-secret" not in json.dumps(data)
