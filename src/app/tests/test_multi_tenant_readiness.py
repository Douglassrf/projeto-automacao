from fastapi.testclient import TestClient

from app.core.multi_tenant_readiness import multi_tenant_readiness
from app.main import app


def test_multi_tenant_readiness_creates_partition_without_storage():
    result = multi_tenant_readiness(
        {
            "tenant": "Acme Ads",
            "workspace": "us-growth",
            "role": "ADMIN",
            "plan": "growth",
            "platform": "google",
            "headline": "Stop wasting ad budget",
            "body": "Use dados e prova social para encontrar criativos antes de escalar.",
            "landing_url": "https://example.com",
            "impressions": 100,
            "niche": "saas",
        }
    )

    assert result["status"] == "tenant_ready"
    assert result["will_execute_real_action"] is False
    assert result["tenant_storage_enabled"] is False
    assert result["tenant"]["data_partition"].startswith("tenant/")
    assert "audit.read" in result["actor"]["permissions"]
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_multi_tenant_readiness_blocks_cross_tenant_access():
    result = multi_tenant_readiness(
        {
            "tenant": "Acme Ads",
            "requested_tenant": "Other Org",
            "workspace": "main",
            "plan": "starter",
            "platform": "meta",
        }
    )

    assert result["status"] == "blocked"
    assert "cross_tenant_access_forbidden" in result["blocked_reasons"]


def test_multi_tenant_readiness_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/multi-tenant-readiness",
            json={"tenant": "Acme Ads", "workspace": "main", "plan": "starter", "platform": "meta"},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37O"
