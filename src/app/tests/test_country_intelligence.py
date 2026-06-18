from fastapi.testclient import TestClient

from app.core.country_intelligence import country_intelligence_profile
from app.main import app


def test_country_intelligence_profiles_tier_one_market():
    result = country_intelligence_profile({"country": "US", "niche": "saas"})

    assert result["status"] == "country_ready"
    assert result["will_execute_real_action"] is False
    assert result["profile"]["currency"] == "USD"
    assert result["recommended_language"] == "en-US"
    assert result["budget_hint"] == "high_ticket_saas"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_country_intelligence_blocks_unsupported_country():
    result = country_intelligence_profile({"country": "XX"})

    assert result["status"] == "blocked"
    assert "unsupported_country" in result["blocked_reasons"]
    assert result["profile"]["market_tier"] == "unknown"


def test_country_intelligence_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/country-profile", json={"country": "BR"})

    assert response.status_code == 200
    assert response.json()["mission"] == "37E"
