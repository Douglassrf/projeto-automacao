from fastapi.testclient import TestClient

from app.main import app


def test_post_execution_monitor_runs_in_dry_run_without_actions():
    payload = {
        "force_dry_run": True,
        "created_resources": [
            {"campaign_id": "dry_campaign_1", "campaign_name": "Campanha Segura", "spend_today": 10.0}
        ],
        "daily_spend_limit_brl": 50.0,
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-operator/production/post-execution-monitor", json=payload)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission_id"] == "post-execution-monitor"
    assert data["status"] == "ok"
    assert data["dry_run"] is True
    assert data["auto_actions_enabled"] is False
    assert data["executed_actions"] == []
    assert data["monitored_campaigns"][0]["status_real"] == "SIMULATED_ACTIVE"


def test_post_execution_monitor_flags_spend_without_pausing_campaign():
    payload = {
        "force_dry_run": True,
        "created_resources": [
            {"campaign_id": "dry_campaign_2", "campaign_name": "Campanha Cara", "spend_today": 75.0}
        ],
        "daily_spend_limit_brl": 50.0,
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-operator/production/post-execution-monitor", json=payload)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "attention"
    assert data["executed_actions"] == []
    assert data["alerts"][0]["reason"] == "SPEND_LIMIT_EXCEEDED"
    assert data["alerts"][0]["recommended_action"] == "pause_campaign_pending_approval"
