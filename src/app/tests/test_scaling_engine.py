from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.core.config import get_settings


def auth_headers(client: TestClient) -> dict[str, str]:
    settings = get_settings()
    response = client.post("/api/v1/auth/login", json={"email": settings.default_admin_email, "password": settings.default_admin_password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_gradual_scaling_engine_creates_pending_scale_action_from_manual_revenue():
    unique = uuid4().hex[:8]
    campaign_id = f"camp-scale-mvp-{unique}"
    with TestClient(app) as client:
        headers = auth_headers(client)
        campaign = client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": campaign_id,
            "meta_campaign_id": f"2385{unique}",
            "meta_adset_id": f"1200{unique}",
            "product_name": "Scale MVP Product",
            "strategy_version": "V2",
            "status": "ACTIVE",
            "daily_budget": 25,
            "desired_budget": 25,
            "real_budget": 25,
            "target_roas": 2,
        }, headers=headers)
        assert campaign.status_code == 200, campaign.text

        rule = client.post("/api/v1/campaign-intelligence/scaling-rules", json={
            "internal_campaign_id": campaign_id,
            "min_roas_threshold": 2.0,
            "excellent_roas_threshold": 4.0,
            "standard_increment_percentage": 10,
            "increment_percentage": 20,
            "max_budget_cap": 5000.0,
            "cooldown_days": 3,
            "min_sales_volume": 1,
        }, headers=headers)
        assert rule.status_code == 200, rule.text

        metric = client.post("/api/v1/campaign-intelligence/metrics", json={
            "internal_campaign_id": campaign_id,
            "ctr": 2.5,
            "spend": 25,
            "purchases": 1,
            "cost_per_purchase": 25,
            "roas": 4.0,
            "connect_rate": 85,
            "capi_status": "ok",
            "source": "dry_run",
        }, headers=headers)
        assert metric.status_code == 200, metric.text

        revenue = client.post("/api/v1/campaign-intelligence/manual-revenue", json={
            "internal_campaign_id": campaign_id,
            "revenue_amount": 20,
            "currency": "EUR",
            "exchange_rate_to_brl": 6.2,
            "sales_count": 1,
            "created_by": "douglas_admin",
        }, headers=headers)
        assert revenue.status_code == 200, revenue.text
        assert revenue.json()["revenue_brl"] == 124

        run = client.post("/api/v1/campaign-intelligence/scaling/run?dry_run=true&limit=100", headers=headers)
        assert run.status_code == 200, run.text
        data = run.json()
        item = [r for r in data["results"] if r["internal_campaign_id"] == campaign_id][0]
        assert item["action"] == "SCALE_BUDGET"
        assert item["reason_code"] == "PERFORMANCE_VALIDATED_SCALE"
        assert item["proposed_budget_brl"] == 30.0
        assert item["action_id"] is not None

        pending = client.get("/api/v1/campaign-intelligence/meta-actions/pending", headers=headers)
        assert pending.status_code == 200, pending.text
        assert any(row["id"] == item["action_id"] and row["action"] == "scale_budget" for row in pending.json())
