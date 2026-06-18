from fastapi.testclient import TestClient

from app.core.data_moat import data_moat_local_snapshot
from app.main import app


def test_data_moat_creates_fingerprints_and_stats_without_writes():
    result = data_moat_local_snapshot(
        {
            "signals": [
                {
                    "platform": "meta",
                    "country": "US",
                    "headline": "Stop wasting ad budget",
                    "body": "Use dados para testar criativos antes de escalar.",
                    "landing_url": "https://example.com",
                    "impressions": 1000,
                    "clicks": 80,
                    "leads": 8,
                    "niche": "saas",
                },
                {
                    "platform": "google",
                    "country": "US",
                    "headline": "Better ad intelligence",
                    "body": "Find creative patterns before scaling campaigns.",
                    "landing_url": "https://example.com",
                    "impressions": 800,
                    "clicks": 40,
                    "leads": 5,
                    "niche": "saas",
                },
            ]
        }
    )

    assert result["status"] == "moat_snapshot_ready"
    assert result["will_execute_real_action"] is False
    assert result["database_write_used"] is False
    assert result["unique_fingerprints"] == 2
    assert result["platform_counts"]["meta"] == 1
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_data_moat_reports_insufficient_data_when_no_valid_signals():
    result = data_moat_local_snapshot({"signals": [{"platform": "unknown"}]})

    assert result["status"] == "insufficient_data"
    assert result["unique_fingerprints"] == 0
    assert result["miner_summary"]["signals_blocked"] == 1


def test_data_moat_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/data-moat-local",
            json={"signals": [{"platform": "meta", "headline": "Teste", "body": "Texto bom para teste", "impressions": 10}]},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37L"
