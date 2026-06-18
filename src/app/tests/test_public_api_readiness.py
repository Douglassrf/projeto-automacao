from fastapi.testclient import TestClient

from app.core.public_api_readiness import public_api_readiness
from app.main import app


def test_public_api_readiness_catalogs_public_safe_endpoints():
    result = public_api_readiness(
        {
            "tenant": "Acme Ads",
            "workspace": "main",
            "plan": "growth",
            "platform": "google",
            "scope": "dashboard.read",
            "headline": "Stop wasting ad budget",
            "body": "Use dados para testar criativos antes de escalar.",
            "landing_url": "https://example.com",
            "impressions": 100,
            "niche": "saas",
        }
    )

    assert result["status"] == "public_api_ready"
    assert result["external_api_published"] is False
    assert len(result["catalog"]) >= 4
    assert result["catalog"][0]["scope"] == "dashboard.read"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_public_api_readiness_blocks_unknown_scope_and_publish_flag():
    result = public_api_readiness({"tenant": "Acme", "workspace": "main", "scope": "execute.real", "publish_external_api": True})

    assert result["status"] == "blocked"
    assert "unknown_public_api_scope" in result["blocked_reasons"]
    assert "external_api_publish_forbidden_in_readiness" in result["blocked_reasons"]


def test_public_api_readiness_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/public-api-readiness",
            json={"tenant": "Acme", "workspace": "main", "scope": "dashboard.read"},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37P"
