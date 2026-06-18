from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.tests.test_meta_campaign_operator import _payload


def test_assisted_execution_gate_blocks_without_explicit_phrase():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/campaign-operator/production/assisted-execution",
            json={"launch_payload": _payload(mode="publish_paused")},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission_id"] == "assisted-execution-gate"
    assert data["status"] == "blocked"
    assert data["published"] is False
    assert data["executed"] is False
    blocked_names = {item["name"] for item in data["blocked_checks"]}
    assert "approval_phrase" in blocked_names


def test_assisted_execution_gate_can_be_ready_without_publishing():
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
            "approval_phrase": "EU APROVO EXECUCAO REAL ASSISTIDA",
        }
        with TestClient(app) as client:
            review = client.post("/api/v1/campaign-operator/production/credential-review", json=payload)
            payload["expected_payload_sha256"] = review.json()["payload_preview"]["payload_sha256"]
            response = client.post("/api/v1/campaign-operator/production/assisted-execution", json=payload)
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ready_for_human_execution"
    assert data["published"] is False
    assert data["executed"] is False
    assert data["would_publish"] is True
    assert data["requires_final_human_action"] is True
    assert len(data["payload_sha256"]) == 64
