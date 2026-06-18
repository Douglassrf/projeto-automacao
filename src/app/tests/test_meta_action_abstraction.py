from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings


def auth_headers(client: TestClient) -> dict[str, str]:
    settings = get_settings()
    response = client.post("/api/v1/auth/login", json={"email": settings.default_admin_email, "password": settings.default_admin_password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_meta_action_abstraction_requires_approval_before_execution():
    with TestClient(app) as client:
        headers = auth_headers(client)
        client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": "cmp-approval-layer",
            "meta_campaign_id": "238500000009001",
            "meta_adset_id": "1200000009001",
            "product_name": "Approval Product",
            "strategy_version": "V3",
            "status": "ACTIVE",
            "daily_budget": 50,
            "target_cpa": 25,
            "target_roas": 2,
        }, headers=headers)

        proposal = client.post("/api/v1/campaign-intelligence/meta-actions/propose", json={
            "internal_campaign_id": "cmp-approval-layer",
            "action": "pause_campaign",
            "target": "campaign",
            "reasoning": "CPA passou da meta e exige aprovação antes de pausar.",
        }, headers=headers)
        assert proposal.status_code == 200, proposal.text
        body = proposal.json()
        assert body["status"] == "pending_approval"
        assert body["payload_hash"]

        blocked = client.post(f"/api/v1/campaign-intelligence/meta-actions/{body['id']}/approve", json={
            "payload_hash": body["payload_hash"],
            "confirmed_by_user": False,
            "approved_by": "qa",
            "dry_run": True,
        }, headers=headers)
        assert blocked.status_code == 400

        approved = client.post(f"/api/v1/campaign-intelligence/meta-actions/{body['id']}/approve", json={
            "payload_hash": body["payload_hash"],
            "confirmed_by_user": True,
            "approved_by": "qa",
            "dry_run": True,
        }, headers=headers)
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"
        assert approved.json()["meta_response"]["status"] == "approved_pending_execution"

        executed = client.post(f"/api/v1/campaign-intelligence/meta-actions/{body['id']}/execute", json={
            "confirmed_by_user": True,
            "dry_run": True,
        }, headers=headers)
        assert executed.status_code == 200, executed.text
        assert executed.json()["status"] == "executed_dry_run"
        assert executed.json()["meta_response"]["dry_run"] is True


def test_campaign_state_sync_detects_no_drift_in_dry_run():
    with TestClient(app) as client:
        headers = auth_headers(client)
        client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": "cmp-state-sync",
            "meta_campaign_id": "238500000009002",
            "product_name": "State Product",
            "strategy_version": "V1",
            "status": "ACTIVE",
            "desired_status": "ACTIVE",
            "daily_budget": 25,
        }, headers=headers)
        response = client.post("/api/v1/campaign-intelligence/campaigns/sync-state", json={
            "internal_campaign_id": "cmp-state-sync"
        }, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["desired_status"] == "ACTIVE"
        assert data["real_status"] == "ACTIVE"
        assert data["divergence_detected"] is False


def test_decision_loop_creates_pending_action_not_meta_write():
    with TestClient(app) as client:
        headers = auth_headers(client)
        client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": "cmp-loop-approval-only",
            "meta_campaign_id": "238500000009901",
            "meta_adset_id": "1200000009901",
            "product_name": "Approval Only Product",
            "strategy_version": "V3",
            "status": "ACTIVE",
            "daily_budget": 10,
            "target_cpa": 25,
            "target_roas": 2,
        }, headers=headers)
        client.post("/api/v1/campaign-intelligence/metrics", json={
            "internal_campaign_id": "cmp-loop-approval-only",
            "spend": 20,
            "purchases": 0,
            "cost_per_purchase": 0,
            "roas": 0,
            "connect_rate": 80,
            "source": "dry_run",
        }, headers=headers)
        response = client.post("/api/v1/campaign-intelligence/decision-loop", json={"dry_run": False, "limit": 100}, headers=headers)
        assert response.status_code == 200, response.text
        match = [r for r in response.json()["results"] if r["internal_campaign_id"] == "cmp-loop-approval-only"][0]
        assert match["action"] == "pause_campaign"
        assert match["executed"] is False
        assert match["meta_response"]["status"] == "pending_approval"

        pending = client.get("/api/v1/campaign-intelligence/meta-actions/pending", headers=headers)
        assert pending.status_code == 200, pending.text
        assert any(row["meta_campaign_id"] == "238500000009901" for row in pending.json())
