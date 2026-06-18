from fastapi.testclient import TestClient

from app.core.ad_library_search import ad_library_search_local
from app.main import app


def _payload():
    return {
        "tenant": "Acme Ads",
        "workspace": "main",
        "plan": "growth",
        "query": "budget",
        "signals": [
            {
                "platform": "google",
                "country": "US",
                "headline": "Stop wasting ad budget",
                "body": "Use dados para testar criativos antes de escalar.",
                "landing_url": "https://example.com",
                "impressions": 100,
                "clicks": 8,
                "niche": "saas",
            },
            {
                "platform": "tiktok",
                "country": "BR",
                "headline": "Receita rapida para afiliados",
                "body": "Teste criativos curtos com controle de risco.",
                "landing_url": "https://example.com/br",
                "impressions": 100,
                "clicks": 4,
                "niche": "affiliate",
            },
        ],
    }


def test_ad_library_search_filters_preview_without_database():
    result = ad_library_search_local(_payload())

    assert result["status"] == "ad_library_search_ready"
    assert result["database_read_used"] is False
    assert result["network_access_used"] is False
    assert result["search_index_built_in_memory"] is True
    assert result["results_count"] == 1
    assert result["results_preview"][0]["platform"] == "google"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_ad_library_search_blocks_external_and_database_search():
    payload = _payload()
    payload["external_search"] = True
    payload["database_search"] = True
    result = ad_library_search_local(payload)

    assert result["status"] == "blocked"
    assert "external_search_forbidden_in_local_readiness" in result["blocked_reasons"]
    assert "database_search_forbidden_in_local_readiness" in result["blocked_reasons"]


def test_ad_library_search_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/ad-library-search", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37U"
