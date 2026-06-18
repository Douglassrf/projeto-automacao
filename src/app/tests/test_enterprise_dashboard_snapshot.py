from fastapi.testclient import TestClient

from app.core.enterprise_dashboard_snapshot import enterprise_dashboard_snapshot
from app.main import app


def _strong_payload():
    return {
        "platform": "meta",
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


def test_enterprise_dashboard_snapshot_returns_safe_cards_and_kpis():
    result = enterprise_dashboard_snapshot(_strong_payload())

    assert result["status"] == "snapshot_ready"
    assert result["will_execute_real_action"] is False
    assert result["will_activate_spend"] is False
    assert result["kpis"]["global_score"] >= 70
    assert len(result["cards"]) == 4
    assert result["operator"]["plan"]["campaign_status"] == "PAUSED"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_enterprise_dashboard_snapshot_surfaces_blockers():
    result = enterprise_dashboard_snapshot({"platform": "unknown", "headline": "", "body": ""})

    assert result["readiness"] == "red"
    assert result["kpis"]["blocked_reasons"] > 0
    assert result["operator"]["status"] == "blocked"


def test_enterprise_dashboard_snapshot_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/enterprise-snapshot", json=_strong_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37J"
