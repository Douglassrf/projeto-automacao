from fastapi.testclient import TestClient

from app.core.frontend_enterprise_spec import frontend_enterprise_spec
from app.main import app


def _payload():
    return {
        "tenant": "Acme Ads",
        "workspace": "main",
        "plan": "growth",
        "platform": "google",
        "scope": "dashboard.read",
        "country": "US",
        "headline": "Stop wasting ad budget",
        "body": "Use dados e prova social para encontrar criativos antes de escalar.",
        "cta": "SIGN_UP",
        "landing_url": "https://example.com",
        "impressions": 100,
        "niche": "saas",
    }


def test_frontend_enterprise_spec_returns_safe_screen_contract():
    result = frontend_enterprise_spec(_payload())

    assert result["status"] == "frontend_spec_ready"
    assert result["frontend_built"] is False
    assert result["will_execute_real_action"] is False
    assert len(result["screens"]) == 5
    assert "tenant" in result["global_filters"]
    assert result["data_sources"]["operator_dry_run"].endswith("/operator-dry-run")
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_frontend_enterprise_spec_blocks_bad_public_scope():
    payload = _payload()
    payload["scope"] = "execute.real"
    result = frontend_enterprise_spec(payload)

    assert result["status"] == "blocked"
    assert "unknown_public_api_scope" in result["blocked_reasons"]


def test_frontend_enterprise_spec_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/frontend-enterprise-spec", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37Q"
