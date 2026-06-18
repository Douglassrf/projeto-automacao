from fastapi.testclient import TestClient

from app.core.commercial_api_snapshot import commercial_api_snapshot
from app.main import app


def _payload(plan="growth", platform="google"):
    return {
        "plan": plan,
        "platform": platform,
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


def test_commercial_api_snapshot_exposes_plan_limits_without_billing():
    result = commercial_api_snapshot(_payload())

    assert result["status"] == "commercial_snapshot_ready"
    assert result["will_execute_real_action"] is False
    assert result["billing_enabled"] is False
    assert result["limits"]["signals_per_day"] == 1000
    assert "google" in result["enabled_platforms"]
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_commercial_api_snapshot_blocks_platform_not_enabled_for_plan():
    result = commercial_api_snapshot(_payload(plan="starter", platform="google"))

    assert result["status"] == "blocked"
    assert "platform_not_enabled_for_plan" in result["blocked_reasons"]
    assert result["limits"]["platforms"] == ["meta"]


def test_commercial_api_snapshot_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/commercial-api-snapshot", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37M"
