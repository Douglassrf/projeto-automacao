from fastapi.testclient import TestClient

from app.core.ad_library_model import ad_library_data_model
from app.main import app


def _payload():
    return {
        "tenant": "Acme Ads",
        "workspace": "main",
        "plan": "growth",
        "platform": "google",
        "headline": "Stop wasting ad budget",
        "body": "Use dados para testar criativos antes de escalar.",
        "landing_url": "https://example.com",
        "impressions": 100,
        "niche": "saas",
        "signals": [
            {
                "platform": "google",
                "country": "US",
                "headline": "Stop wasting ad budget",
                "body": "Use dados para testar criativos antes de escalar.",
                "landing_url": "https://example.com",
                "impressions": 100,
                "niche": "saas",
            }
        ],
    }


def test_ad_library_model_defines_safe_schema_without_persistence():
    result = ad_library_data_model(_payload())

    assert result["status"] == "ad_library_model_ready"
    assert result["database_write_used"] is False
    assert result["large_local_storage_used"] is False
    assert result["storage_plan"]["local_preview_path"] == "data/ad_library/"
    assert result["storage_plan"]["zip_includes_data"] is False
    assert "ads" in result["schema"]
    assert "ad_vectors" in result["schema"]
    assert len(result["records_preview"]) == 1
    assert result["records_preview"][0]["tenant_id"] == result["tenant"]["tenant_id"]
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_ad_library_model_blocks_sensitive_payload_and_local_persistence():
    payload = _payload()
    payload["persist_ads"] = True
    payload["access_token"] = "secret-token"
    result = ad_library_data_model(payload)

    assert result["status"] == "blocked"
    assert "ad_library_persistence_forbidden_in_local_readiness" in result["blocked_reasons"]
    assert "sensitive_fields_forbidden_in_ad_library_payload" in result["blocked_reasons"]
    assert "access_token" in result["sensitive_keys_detected"]


def test_ad_library_model_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/ad-library-model", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37T"
