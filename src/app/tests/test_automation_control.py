from fastapi.testclient import TestClient

from app.main import app


def _payload(**overrides):
    data = {
        "campaign_id": "campanha_teste_001",
        "adset_id": "conjunto_teste_001",
        "action": "pause_campaign",
        "target": "campaign",
        "reason_code": "ZERO_PURCHASE_GUARD",
        "metric_name": "spend_without_purchase",
        "metric_value": 25,
        "threshold_value": 25,
        "daily_spend_brl": 25,
        "current_purchases": 0,
        "confirmed_by_user": True,
        "force_dry_run": True,
    }
    data.update(overrides)
    return data


def test_automation_control_status():
    with TestClient(app) as client:
        response = client.get("/api/v1/automation-control/status")
    assert response.status_code == 200
    data = response.json()
    assert data["automation_level"] in [0, 1, 2]
    assert "notify_only" in data["allowed_actions"]


def test_level_zero_blocks_real_action_and_logs_decision():
    with TestClient(app) as client:
        response = client.post("/api/v1/automation-control/apply-suggestion", json=_payload())
    assert response.status_code == 200
    data = response.json()
    assert data["blocked"] is True
    assert data["action_executed"] is False
    assert data["decision_log_id"] is not None
    assert "Nível 0" in data["blocked_reason"]


def test_notify_only_is_allowed_in_level_zero():
    with TestClient(app) as client:
        response = client.post("/api/v1/automation-control/apply-suggestion", json=_payload(action="notify_only"))
    assert response.status_code == 200
    data = response.json()
    assert data["blocked"] is False
    assert data["action_executed"] is False
    assert data["meta_response"]["status"] == "notified"
