from fastapi.testclient import TestClient

from app.core.release_readiness import release_readiness_local
from app.main import app


def _payload():
    return {
        "tenant": "Acme Ads",
        "workspace": "main",
        "plan": "growth",
        "regions": ["BR", "US"],
        "retention_days": 180,
        "platform": "google",
        "country": "US",
        "headline": "Stop wasting ad budget",
        "body": "Use dados para testar criativos antes de escalar com seguranca.",
        "cta": "SIGN_UP",
        "landing_url": "https://example.com",
        "impressions": 1000,
        "clicks": 140,
        "conversions": 25,
        "spend": 100,
        "niche": "saas",
        "trend_score": 95,
        "frequency": 1.4,
        "ctr_drop_percent": 0,
        "signals": [
            {
                "platform": "google",
                "country": "US",
                "headline": "Stop wasting ad budget",
                "body": "Use dados para testar criativos antes de escalar com seguranca.",
                "landing_url": "https://example.com",
                "impressions": 1000,
                "clicks": 140,
                "conversions": 25,
                "spend": 100,
                "niche": "saas",
            }
        ],
    }


def test_release_readiness_builds_safe_gate_without_deploy():
    result = release_readiness_local(_payload())

    assert result["mission"] == "38A"
    assert result["deploy_used"] is False
    assert result["billing_enabled"] is False
    assert result["real_meta_enabled"] is False
    assert result["checklist"]["tests_expected"] == "258 passed"
    assert result["release_gate"] == "human_review_only"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_release_readiness_blocks_activation_flags():
    payload = _payload()
    payload["deploy_now"] = True
    payload["enable_billing"] = True
    payload["enable_public_api"] = True
    payload["enable_real_meta"] = True
    result = release_readiness_local(payload)

    assert result["status"] == "blocked"
    assert "deploy_forbidden_in_release_readiness" in result["blocked_reasons"]
    assert "billing_activation_forbidden_in_release_readiness" in result["blocked_reasons"]
    assert "public_api_activation_forbidden_in_release_readiness" in result["blocked_reasons"]
    assert "real_meta_activation_forbidden_in_release_readiness" in result["blocked_reasons"]


def test_release_readiness_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/release-readiness", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "38A"
