from fastapi.testclient import TestClient

from app.core.landing_intelligence import landing_intelligence_analysis
from app.main import app


def test_landing_intelligence_scores_safe_lead_landing():
    result = landing_intelligence_analysis(
        {
            "platform": "meta",
            "headline": "Teste landing",
            "body": "Pagina segura para capturar lead qualificado.",
            "cta": "SIGN_UP",
            "landing_url": "https://example.com/lead",
            "funnel_type": "lead",
            "impressions": 100,
        }
    )

    assert result["status"] == "landing_ready"
    assert result["will_execute_real_action"] is False
    assert result["analysis"]["is_https"] is True
    assert result["analysis"]["lead_ready"] is True
    assert result["analysis"]["landing_score"] >= 75
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_landing_intelligence_flags_weak_landing():
    result = landing_intelligence_analysis(
        {
            "platform": "meta",
            "headline": "Teste",
            "body": "Texto suficiente para normalizar o sinal.",
            "landing_url": "http://localhost",
            "impressions": 100,
        }
    )

    assert result["status"] == "needs_revision"
    assert "landing_not_https" in result["analysis"]["risk_flags"]
    assert "landing_domain_invalid" in result["analysis"]["risk_flags"]


def test_landing_intelligence_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/landing-analysis",
            json={
                "platform": "meta",
                "headline": "Teste",
                "body": "Texto bom para teste",
                "landing_url": "https://example.com",
                "impressions": 10,
            },
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37F"
