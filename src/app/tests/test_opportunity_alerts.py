from fastapi.testclient import TestClient

from app.core.opportunity_alerts import opportunity_alerts_local
from app.main import app


def _payload():
    return {
        "tenant": "Acme Ads",
        "workspace": "main",
        "plan": "growth",
        "regions": ["BR", "US"],
        "query": "budget",
        "platform": "google",
        "country": "US",
        "headline": "Stop wasting ad budget",
        "body": "Use dados para testar criativos antes de escalar com seguranca.",
        "cta": "SIGN_UP",
        "landing_url": "https://example.com",
        "impressions": 1000,
        "clicks": 120,
        "conversions": 20,
        "spend": 100,
        "niche": "saas",
        "trend_score": 90,
        "signals": [
            {
                "platform": "google",
                "country": "US",
                "headline": "Stop wasting ad budget",
                "body": "Use dados para testar criativos antes de escalar com seguranca.",
                "landing_url": "https://example.com",
                "impressions": 1000,
                "clicks": 120,
                "conversions": 20,
                "spend": 100,
                "niche": "saas",
            }
        ],
    }


def test_opportunity_alerts_prioritizes_local_alerts_without_notifications():
    result = opportunity_alerts_local(_payload())

    assert result["mission"] == "37X"
    assert result["external_notification_used"] is False
    assert result["auto_campaign_created"] is False
    assert result["alerts_count"] >= 1
    assert result["source_modules"]["executive_report"] == "37W"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_opportunity_alerts_blocks_external_delivery_and_auto_campaign():
    payload = _payload()
    payload["send_webhook"] = True
    payload["send_email"] = True
    payload["auto_create_campaign"] = True
    result = opportunity_alerts_local(payload)

    assert result["status"] == "blocked"
    assert "webhook_delivery_forbidden_in_local_readiness" in result["blocked_reasons"]
    assert "email_delivery_forbidden_in_local_readiness" in result["blocked_reasons"]
    assert "auto_campaign_creation_forbidden_in_alerts" in result["blocked_reasons"]


def test_opportunity_alerts_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/opportunity-alerts", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37X"
