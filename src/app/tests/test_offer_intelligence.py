from fastapi.testclient import TestClient

from app.core.offer_intelligence import offer_intelligence_analysis
from app.main import app


def test_offer_intelligence_scores_premium_recurring_offer():
    result = offer_intelligence_analysis(
        {
            "platform": "google",
            "headline": "Scale better ad decisions",
            "body": "Use dados e prova social para melhorar criativos antes de escalar.",
            "landing_url": "https://example.com",
            "impressions": 100,
            "niche": "saas",
            "ticket": 99,
            "recurrence": "monthly",
            "proof": "case study",
        }
    )

    assert result["status"] == "offer_ready"
    assert result["will_execute_real_action"] is False
    assert result["analysis"]["market_fit"] == "premium_recurring"
    assert result["analysis"]["offer_score"] >= 70
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_offer_intelligence_flags_risky_offer_claims():
    result = offer_intelligence_analysis(
        {
            "platform": "meta",
            "headline": "Lucro 100% garantido",
            "body": "dinheiro facil sem esforco",
            "landing_url": "https://example.com",
            "impressions": 100,
            "niche": "unknown",
            "ticket": 10,
        }
    )

    assert result["status"] == "needs_revision"
    assert "risky_offer_claim" in result["analysis"]["risk_flags"]
    assert "niche_unknown" in result["analysis"]["risk_flags"]


def test_offer_intelligence_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/offer-analysis",
            json={"platform": "meta", "headline": "Oferta", "body": "Texto bom para oferta", "impressions": 10, "niche": "saas"},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37G"
