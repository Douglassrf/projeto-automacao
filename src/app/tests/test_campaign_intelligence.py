from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings


def auth_headers(client: TestClient) -> dict[str, str]:
    settings = get_settings()
    response = client.post("/api/v1/auth/login", json={"email": settings.default_admin_email, "password": settings.default_admin_password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_campaign_intelligence_migration_and_decision_loop():
    with TestClient(app) as client:
        headers = auth_headers(client)

        health = client.get("/api/v1/campaign-intelligence/health", headers=headers)
        assert health.status_code == 200, health.text
        assert health.json()["schema_keys"]["meta_link_key"] == "campaigns.meta_campaign_id"

        campaign_payload = {
            "internal_campaign_id": "cmp-local-v3-001",
            "meta_campaign_id": "238500000000001",
            "product_id": "prod-001",
            "product_name": "Diabetes Control",
            "strategy_version": "V3",
            "daily_budget": 25,
            "spend_today": 0,
            "target_cpa": 30,
            "target_roas": 2,
        }
        campaign = client.post("/api/v1/campaign-intelligence/campaigns", json=campaign_payload, headers=headers)
        assert campaign.status_code == 200, campaign.text
        assert campaign.json()["meta_campaign_id"] == "238500000000001"

        benchmark = client.post("/api/v1/campaign-intelligence/benchmarks", json={
            "niche": "Diabetes Control",
            "geo": "LATAM",
            "language": "Spanish_All",
            "creative_pattern": "UGC fear hook",
            "hook_pattern": "problema imediato",
            "days_active": 45,
            "estimated_strength_score": 91,
            "benchmark_ctr": 1.8,
            "source_ad_id": "adlib-001",
        }, headers=headers)
        assert benchmark.status_code == 200, benchmark.text

        metric = client.post("/api/v1/campaign-intelligence/metrics", json={
            "meta_campaign_id": "238500000000001",
            "ctr": 2.4,
            "cpc": 0.12,
            "cpm": 6.0,
            "spend": 22,
            "purchases": 1,
            "cost_per_purchase": 22,
            "roas": 2.4,
            "connect_rate": 84,
            "checkout_rate": 18,
            "capi_status": "ok",
            "source": "dry_run",
        }, headers=headers)
        assert metric.status_code == 200, metric.text

        decision = client.post("/api/v1/campaign-intelligence/evaluate", json={
            "meta_campaign_id": "238500000000001",
            "niche": "Diabetes Control",
            "geo": "LATAM",
        }, headers=headers)
        assert decision.status_code == 200, decision.text
        body = decision.json()
        assert body["health_color"] == "green"
        assert "scale_budget_20" in body["recommended_actions"]


def test_campaign_intelligence_crisis_generates_red_and_yellow_tickets():
    with TestClient(app) as client:
        headers = auth_headers(client)
        campaign = client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": "cmp-crisis-v1",
            "meta_campaign_id": "238500000000099",
            "product_name": "Oferta Teste",
            "strategy_version": "V1",
            "daily_budget": 25,
            "target_cpa": 20,
            "target_roas": 1.5,
        }, headers=headers)
        assert campaign.status_code == 200, campaign.text

        metric = client.post("/api/v1/campaign-intelligence/metrics", json={
            "internal_campaign_id": "cmp-crisis-v1",
            "ctr": 0.5,
            "spend": 50,
            "purchases": 1,
            "cost_per_purchase": 50,
            "roas": 0.7,
            "connect_rate": 42,
            "capi_status": "error",
            "source": "csv",
        }, headers=headers)
        assert metric.status_code == 200, metric.text

        decision = client.post("/api/v1/campaign-intelligence/evaluate", json={"internal_campaign_id": "cmp-crisis-v1"}, headers=headers)
        assert decision.status_code == 200, decision.text
        body = decision.json()
        assert body["health_color"] == "red"
        assert "pause_campaign" in body["recommended_actions"]
        assert "activate_capi_fallback" in body["recommended_actions"]
        assert "fix_landing_page" in body["recommended_actions"]


def test_campaign_decision_loop_pauses_budget_overrun_in_dry_run():
    with TestClient(app) as client:
        headers = auth_headers(client)
        client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": "cmp-loop-budget",
            "meta_campaign_id": "238500000000777",
            "meta_adset_id": "1200000000777",
            "product_name": "Budget Guard Product",
            "strategy_version": "V3",
            "status": "ACTIVE",
            "daily_budget": 25,
            "target_cpa": 30,
            "target_roas": 2,
        }, headers=headers)
        client.post("/api/v1/campaign-intelligence/metrics", json={
            "internal_campaign_id": "cmp-loop-budget",
            "spend": 35,
            "purchases": 0,
            "cost_per_purchase": 0,
            "roas": 0,
            "connect_rate": 80,
            "source": "dry_run",
        }, headers=headers)
        response = client.post("/api/v1/campaign-intelligence/decision-loop", json={"dry_run": True, "limit": 100}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        match = [r for r in body["results"] if r["internal_campaign_id"] == "cmp-loop-budget"][0]
        assert match["reason_code"] == "PAUSADA_POR_ESTOURO_ORCAMENTO"
        assert match["action"] == "pause_campaign"
        assert match["dry_run"] is True


def test_campaign_decision_loop_decreases_bid_when_cpa_above_target():
    with TestClient(app) as client:
        headers = auth_headers(client)
        client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": "cmp-loop-cpa",
            "meta_campaign_id": "238500000000778",
            "meta_adset_id": "1200000000778",
            "product_name": "CPA Guard Product",
            "strategy_version": "V2",
            "status": "ACTIVE",
            "daily_budget": 50,
            "target_cpa": 20,
            "target_roas": 2,
        }, headers=headers)
        client.post("/api/v1/campaign-intelligence/metrics", json={
            "internal_campaign_id": "cmp-loop-cpa",
            "spend": 30,
            "purchases": 1,
            "cost_per_purchase": 35,
            "roas": 0.9,
            "connect_rate": 86,
            "source": "dry_run",
        }, headers=headers)
        response = client.post("/api/v1/campaign-intelligence/decision-loop", json={"dry_run": True, "meta_cpa_ideal": 20, "limit": 100}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        match = [r for r in body["results"] if r["internal_campaign_id"] == "cmp-loop-cpa"][0]
        assert match["reason_code"] == "AJUSTE_DE_BID_AUTOMATICO"
        assert match["action"] == "decrease_bid"
        assert match["dry_run"] is True


def test_multi_currency_roi_engine_converts_revenue_to_brl_for_scale_decision():
    with TestClient(app) as client:
        headers = auth_headers(client)
        campaign = client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": "cmp-fx-scale",
            "meta_campaign_id": "238500000000888",
            "meta_adset_id": "1200000000888",
            "product_name": "Euro Offer",
            "strategy_version": "V3",
            "status": "ACTIVE",
            "daily_budget": 25,
            "desired_budget": 25,
            "currency_code": "BRL",
            "currency_ad_account": "BRL",
            "currency_sales": "EUR",
            "target_cpa": 30,
            "target_roas": 2,
        }, headers=headers)
        assert campaign.status_code == 200, campaign.text

        metric = client.post("/api/v1/campaign-intelligence/metrics", json={
            "internal_campaign_id": "cmp-fx-scale",
            "ctr": 2.8,
            "spend": 25,
            "purchases": 1,
            "cost_per_purchase": 25,
            "roas": 1.0,
            "revenue_amount": 20,
            "revenue_currency": "EUR",
            "exchange_rate_to_brl": 5.5,
            "connect_rate": 88,
            "source": "dry_run",
        }, headers=headers)
        assert metric.status_code == 200, metric.text
        metric_body = metric.json()
        assert metric_body["revenue_brl"] == 110
        assert metric_body["unified_roas_brl"] == 4.4

        response = client.post("/api/v1/campaign-intelligence/decision-loop", json={"dry_run": True, "limit": 100}, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        match = [r for r in body["results"] if r["internal_campaign_id"] == "cmp-fx-scale"][0]
        assert match["reason_code"] == "SCALE_BUDGET_TO_50_BRL"
        assert match["action"] == "scale_budget"
        assert "ROAS unificado BRL" in match["reasoning"]


def test_financial_metrics_endpoint_blocks_scale_without_valid_fx():
    with TestClient(app) as client:
        headers = auth_headers(client)
        client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": "cmp-fx-block",
            "meta_campaign_id": "238500000000889",
            "meta_adset_id": "1200000000889",
            "product_name": "Euro Offer Missing FX",
            "strategy_version": "V3",
            "status": "ACTIVE",
            "daily_budget": 25,
            "desired_budget": 25,
            "currency_ad_account": "BRL",
            "currency_sales": "EUR",
            "target_cpa": 30,
            "target_roas": 2,
        }, headers=headers)
        client.post("/api/v1/campaign-intelligence/metrics", json={
            "internal_campaign_id": "cmp-fx-block",
            "ctr": 3.0,
            "spend": 25,
            "purchases": 1,
            "cost_per_purchase": 25,
            "roas": 1.0,
            "revenue_amount": 0,
            "revenue_currency": "EUR",
            "exchange_rate_to_brl": 0,
            "connect_rate": 88,
            "source": "dry_run",
        }, headers=headers)
        response = client.post("/api/v1/campaign-intelligence/decision-loop", json={"dry_run": True, "limit": 100}, headers=headers)
        assert response.status_code == 200, response.text
        match = [r for r in response.json()["results"] if r["internal_campaign_id"] == "cmp-fx-block"][0]
        assert match["reason_code"] == "FX_RATE_MISSING_BLOCK_SCALE"
        assert match["action"] == "monitor"


def test_financial_metrics_endpoint_allows_scale_with_valid_revenue_fx():
    with TestClient(app) as client:
        headers = auth_headers(client)
        client.post("/api/v1/campaign-intelligence/campaigns", json={
            "internal_campaign_id": "cmp-financial-scale",
            "meta_campaign_id": "238500000000890",
            "meta_adset_id": "1200000000890",
            "product_name": "USD Offer",
            "strategy_version": "V3",
            "status": "ACTIVE",
            "daily_budget": 25,
            "desired_budget": 25,
            "currency_ad_account": "BRL",
            "currency_sales": "USD",
            "target_cpa": 30,
            "target_roas": 2,
        }, headers=headers)
        fm = client.post("/api/v1/campaign-intelligence/financial-metrics", json={
            "internal_campaign_id": "cmp-financial-scale",
            "spend_brl": 25,
            "revenue_amount": 20,
            "revenue_currency": "USD",
            "exchange_rate": 5.0,
            "exchange_rate_source": "manual",
            "raw_payload": {"checkout": "test"}
        }, headers=headers)
        assert fm.status_code == 200, fm.text
        assert fm.json()["revenue_brl"] == 100
        assert fm.json()["calculated_roas_brl"] == 4
        assert fm.json()["fx_validated"] is True

        client.post("/api/v1/campaign-intelligence/metrics", json={
            "internal_campaign_id": "cmp-financial-scale",
            "ctr": 3.0,
            "spend": 25,
            "purchases": 1,
            "cost_per_purchase": 25,
            "roas": 1.0,
            "connect_rate": 88,
            "source": "dry_run",
        }, headers=headers)
        response = client.post("/api/v1/campaign-intelligence/decision-loop", json={"dry_run": True, "limit": 100}, headers=headers)
        assert response.status_code == 200, response.text
        match = [r for r in response.json()["results"] if r["internal_campaign_id"] == "cmp-financial-scale"][0]
        assert match["reason_code"] == "SCALE_BUDGET_TO_50_BRL"
        assert match["action"] == "scale_budget"
        assert "ROAS real em BRL" in match["reasoning"]
