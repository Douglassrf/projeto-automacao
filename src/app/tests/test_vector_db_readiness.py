from fastapi.testclient import TestClient

from app.core.vector_db_readiness import vector_db_readiness
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


def test_vector_db_readiness_prepares_local_preview_without_connection():
    result = vector_db_readiness(_payload())

    assert result["status"] == "vector_readiness_ready"
    assert result["vector_db_connected"] is False
    assert result["paid_embeddings_generated"] is False
    assert result["storage_plan"]["local_preview_path"] == "data/vector_memory/"
    assert result["storage_plan"]["zip_includes_data"] is False
    assert len(result["documents_preview"]) == 1
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_vector_db_readiness_blocks_real_connection_and_paid_embeddings():
    payload = _payload()
    payload["connect_vector_db"] = True
    payload["generate_paid_embeddings"] = True
    result = vector_db_readiness(payload)

    assert result["status"] == "blocked"
    assert "vector_db_connection_forbidden_in_readiness" in result["blocked_reasons"]
    assert "paid_embeddings_forbidden_in_readiness" in result["blocked_reasons"]


def test_vector_db_readiness_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/vector-db-readiness", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37S"
