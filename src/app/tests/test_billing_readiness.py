from fastapi.testclient import TestClient

from app.core.billing_readiness import billing_readiness_local
from app.main import app


def test_billing_readiness_returns_preview_without_real_charge():
    result = billing_readiness_local(
        {
            "plan": "growth",
            "platform": "google",
            "headline": "Stop wasting ad budget",
            "body": "Use dados e prova social para encontrar criativos antes de escalar.",
            "landing_url": "https://example.com",
            "impressions": 100,
            "niche": "saas",
        }
    )

    assert result["status"] == "billing_preview_ready"
    assert result["will_charge_customer"] is False
    assert result["billing_provider_connected"] is False
    assert result["invoice_preview"]["monthly_price"] == 199
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_billing_readiness_blocks_real_billing_flag():
    result = billing_readiness_local({"plan": "growth", "enable_real_billing": True})

    assert result["status"] == "blocked"
    assert "real_billing_forbidden_in_local_readiness" in result["blocked_reasons"]
    assert result["invoice_preview"]["will_charge"] is False


def test_billing_readiness_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/billing-readiness", json={"plan": "starter"})

    assert response.status_code == 200
    assert response.json()["mission"] == "37N"
