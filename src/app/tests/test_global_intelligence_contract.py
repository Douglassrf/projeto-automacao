from fastapi.testclient import TestClient

from app.core.global_intelligence_contract import normalize_global_ad_signal
from app.main import app


def test_global_intelligence_contract_normalizes_cross_platform_signal():
    result = normalize_global_ad_signal(
        {
            "platform": "TikTok",
            "country": "us",
            "language": "en-US",
            "currency": "usd",
            "title": "Stop wasting ad budget",
            "description": "Find winning creative before scaling.",
            "call_to_action": "SIGN_UP",
            "destination_url": "https://example.com",
            "impressions": 1000,
            "clicks": 50,
            "spend": 25,
            "leads": 5,
            "vertical": "saas",
        }
    )

    assert result["status"] == "normalized"
    assert result["will_execute_real_action"] is False
    assert result["normalized_signal"]["platform"] == "tiktok"
    assert result["normalized_signal"]["country"] == "US"
    assert result["normalized_signal"]["metrics"]["ctr_percent"] == 5
    assert result["normalized_signal"]["metrics"]["cpa"] == 5
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_global_intelligence_contract_blocks_bad_or_unknown_signal():
    result = normalize_global_ad_signal({"platform": "unknown", "body": "texto", "impressions": -1})

    assert result["status"] == "blocked"
    assert "unsupported_platform" in result["blocked_reasons"]
    assert "headline_required" in result["blocked_reasons"]
    assert "negative_metric_forbidden" in result["blocked_reasons"]


def test_global_intelligence_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/normalize-ad",
            json={"platform": "meta", "headline": "Teste", "body": "Texto", "impressions": 10},
        )

    assert response.status_code == 200
    assert response.json()["universal_contract"]["brain_safe"] is True
