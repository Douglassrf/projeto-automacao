from fastapi.testclient import TestClient

from app.core.real_connectors_readiness import real_connectors_readiness
from app.main import app


def test_real_connectors_readiness_lists_requirements_without_network():
    result = real_connectors_readiness(
        {
            "tenant": "Acme Ads",
            "workspace": "main",
            "plan": "enterprise",
            "platform": "meta",
            "scope": "dashboard.read",
            "platforms": ["meta", "google", "tiktok"],
        }
    )

    assert result["status"] == "connectors_readiness_ready"
    assert result["network_access_used"] is False
    assert result["credentials_loaded"] is False
    assert len(result["connectors"]) == 3
    assert result["connectors"][0]["real_write_enabled"] is False
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_real_connectors_readiness_blocks_network_or_credentials():
    result = real_connectors_readiness({"tenant": "Acme", "workspace": "main", "enable_network": True, "load_credentials": True})

    assert result["status"] == "blocked"
    assert "network_enable_forbidden_in_readiness" in result["blocked_reasons"]
    assert "credential_loading_forbidden_in_readiness" in result["blocked_reasons"]


def test_real_connectors_readiness_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/real-connectors-readiness", json={"tenant": "Acme", "workspace": "main"})

    assert response.status_code == 200
    assert response.json()["mission"] == "37R"
