from fastapi.testclient import TestClient

from app.core.creative_intelligence import creative_intelligence_analysis
from app.main import app


def test_creative_intelligence_detects_angle_emotion_and_score():
    result = creative_intelligence_analysis(
        {
            "platform": "meta",
            "headline": "Stop wasting ad budget",
            "body": "Testei criativos com dados e encontrei o angulo que escala melhor.",
            "cta": "SIGN_UP",
            "format": "short_video",
            "landing_url": "https://example.com",
            "impressions": 100,
            "niche": "saas",
        }
    )

    assert result["status"] == "creative_ready"
    assert result["will_execute_real_action"] is False
    assert result["analysis"]["angle"] == "proof_driven"
    assert result["analysis"]["dominant_emotion"] in {"fear", "gain", "curiosity"}
    assert result["analysis"]["creative_score"] >= 70
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_creative_intelligence_flags_risky_claims():
    result = creative_intelligence_analysis(
        {
            "platform": "meta",
            "headline": "Lucro 100% garantido",
            "body": "dinheiro facil",
            "landing_url": "https://example.com",
            "impressions": 100,
        }
    )

    assert result["status"] == "needs_revision"
    assert "risky_absolute_or_income_claim" in result["analysis"]["risk_flags"]
    assert "body_too_short" in result["analysis"]["risk_flags"]


def test_creative_intelligence_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/creative-analysis",
            json={"platform": "meta", "headline": "Headline boa", "body": "Texto bom para teste", "impressions": 10},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37D"
