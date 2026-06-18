from fastapi.testclient import TestClient

from app.core.scale_forecast import scale_forecast_local
from app.main import app


def _payload():
    return {
        "tenant": "Acme Ads",
        "workspace": "main",
        "plan": "growth",
        "platform": "google",
        "country": "US",
        "headline": "Stop wasting ad budget",
        "body": "Use dados para testar criativos antes de escalar com seguranca.",
        "cta": "SIGN_UP",
        "landing_url": "https://example.com",
        "impressions": 1000,
        "clicks": 140,
        "conversions": 25,
        "spend": 100,
        "niche": "saas",
        "trend_score": 95,
        "frequency": 1.4,
        "ctr_drop_percent": 0,
        "current_budget_brl": 5,
        "signals": [
            {
                "platform": "google",
                "country": "US",
                "headline": "Stop wasting ad budget",
                "body": "Use dados para testar criativos antes de escalar com seguranca.",
                "landing_url": "https://example.com",
                "impressions": 1000,
                "clicks": 140,
                "conversions": 25,
                "spend": 100,
                "niche": "saas",
            }
        ],
    }


def test_scale_forecast_suggests_review_without_applying_budget():
    result = scale_forecast_local(_payload())

    assert result["mission"] == "37Z"
    assert result["budget_change_applied"] is False
    assert result["meta_api_called"] is False
    assert result["human_approval_required"] is True
    assert result["forecast"]["proposed_review_budget_brl"] >= result["forecast"]["current_budget_brl"]
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_scale_forecast_blocks_real_scale_actions():
    payload = _payload()
    payload["apply_budget_change"] = True
    payload["create_scale_action"] = True
    payload["call_meta_api"] = True
    result = scale_forecast_local(payload)

    assert result["status"] == "blocked"
    assert "budget_change_forbidden_in_forecast" in result["blocked_reasons"]
    assert "scale_action_creation_forbidden_in_forecast" in result["blocked_reasons"]
    assert "meta_api_call_forbidden_in_forecast" in result["blocked_reasons"]


def test_scale_forecast_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/scale-forecast", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37Z"
