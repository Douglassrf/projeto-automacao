from fastapi.testclient import TestClient

from app.core.global_operator_hub import global_operator_dry_run
from app.main import app


def test_global_operator_hub_prepares_dry_run_plan_only():
    result = global_operator_dry_run(
        {
            "platform": "meta",
            "action": "prepare_campaign",
            "country": "US",
            "headline": "Stop wasting ad budget",
            "body": "Use dados e prova social para encontrar criativos antes de escalar.",
            "cta": "SIGN_UP",
            "format": "short_video",
            "landing_url": "https://example.com/lead",
            "funnel_type": "lead",
            "impressions": 1000,
            "clicks": 80,
            "spend": 40,
            "leads": 8,
            "niche": "saas",
            "ticket": 99,
            "recurrence": "monthly",
            "proof": "case study",
            "trend_score": 85,
        }
    )

    assert result["will_execute_real_action"] is False
    assert result["will_activate_spend"] is False
    assert result["ready_for_operator"] is False
    assert result["operator_plan"]["campaign_status"] == "PAUSED"
    assert result["operator_plan"]["execution_mode"] == "dry_run_only"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_global_operator_hub_blocks_unsafe_budget_or_bad_brief():
    result = global_operator_dry_run({"platform": "meta", "daily_budget_brl": 50, "headline": "", "body": ""})

    assert result["status"] == "blocked"
    assert "dry_run_budget_above_initial_limit" in result["blocked_reasons"]
    assert "brief_not_ready_for_operator" in result["blocked_reasons"]


def test_global_operator_hub_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/operator-dry-run",
            json={"platform": "meta", "headline": "Teste", "body": "Texto bom para teste", "landing_url": "https://example.com", "impressions": 10, "niche": "saas"},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37I"
