from fastapi.testclient import TestClient

from app.core.saas_compliance import saas_compliance_local
from app.main import app


def _payload():
    return {
        "tenant": "Acme Ads",
        "workspace": "main",
        "plan": "growth",
        "regions": ["BR", "US", "DE"],
        "retention_days": 180,
        "data_types": ["ad_metadata", "metrics", "creative_text"],
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


def test_saas_compliance_maps_regions_without_real_actions():
    result = saas_compliance_local(_payload())

    assert result["status"] == "compliance_ready"
    assert result["network_access_used"] is False
    assert result["database_write_used"] is False
    assert "LGPD" in result["frameworks"]
    assert "GDPR" in result["frameworks"]
    assert result["legal_review_completed"] is False
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_saas_compliance_blocks_sensitive_data_and_real_scraping():
    payload = _payload()
    payload["enable_real_scraping"] = True
    payload["export_personal_data"] = True
    payload["data_types"] = ["ad_metadata", "token", "cpf"]
    payload["retention_days"] = 999
    result = saas_compliance_local(payload)

    assert result["status"] == "blocked"
    assert "real_scraping_requires_legal_review" in result["blocked_reasons"]
    assert "personal_data_export_requires_approval" in result["blocked_reasons"]
    assert "forbidden_sensitive_data_type" in result["blocked_reasons"]


def test_saas_compliance_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/saas-compliance", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37V"
