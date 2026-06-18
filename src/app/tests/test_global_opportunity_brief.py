from fastapi.testclient import TestClient

from app.core.global_opportunity_brief import global_opportunity_brief
from app.main import app


def test_global_opportunity_brief_combines_all_intelligence_sections():
    result = global_opportunity_brief(
        {
            "platform": "google",
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

    assert result["mission"] == "37H"
    assert result["will_execute_real_action"] is False
    assert result["summary"]["ready_sections"] == 4
    assert result["summary"]["global_score"] >= 70
    assert result["sections"]["offer"]["status"] == "offer_ready"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_global_opportunity_brief_keeps_risky_offer_in_revision():
    result = global_opportunity_brief(
        {
            "platform": "meta",
            "country": "BR",
            "headline": "Lucro 100% garantido",
            "body": "dinheiro facil sem esforco",
            "landing_url": "http://localhost",
            "impressions": 100,
            "niche": "unknown",
        }
    )

    assert result["status"] == "needs_revision"
    assert "risky_offer_claim" in result["risk_flags"]
    assert result["ready_for_operator"] is False


def test_global_opportunity_brief_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/opportunity-brief",
            json={"platform": "meta", "country": "BR", "headline": "Teste", "body": "Texto bom para teste", "landing_url": "https://example.com", "impressions": 10, "niche": "saas"},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37H"
