from fastapi.testclient import TestClient

from app.core.executive_reports import executive_report_local
from app.main import app


def _payload():
    return {
        "tenant": "Acme Ads",
        "workspace": "main",
        "plan": "growth",
        "regions": ["BR", "US"],
        "retention_days": 180,
        "query": "budget",
        "headline": "Stop wasting ad budget",
        "body": "Use dados para testar criativos antes de escalar.",
        "landing_url": "https://example.com",
        "impressions": 1000,
        "clicks": 100,
        "niche": "saas",
        "signals": [
            {
                "platform": "google",
                "country": "US",
                "headline": "Stop wasting ad budget",
                "body": "Use dados para testar criativos antes de escalar.",
                "landing_url": "https://example.com",
                "impressions": 1000,
                "clicks": 100,
                "niche": "saas",
            }
        ],
    }


def test_executive_report_consolidates_modules_without_export():
    result = executive_report_local(_payload())

    assert result["mission"] == "37W"
    assert result["external_export_used"] is False
    assert result["network_access_used"] is False
    assert len(result["report"]["sections"]) == 3
    assert result["source_modules"]["compliance"] == "37V"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_executive_report_blocks_external_exports():
    payload = _payload()
    payload["export_pdf"] = True
    payload["send_email"] = True
    payload["share_public_link"] = True
    result = executive_report_local(payload)

    assert result["status"] == "blocked"
    assert "pdf_export_forbidden_in_local_readiness" in result["blocked_reasons"]
    assert "email_delivery_forbidden_in_local_readiness" in result["blocked_reasons"]
    assert "public_link_forbidden_in_local_readiness" in result["blocked_reasons"]


def test_executive_report_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/executive-report", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37W"
