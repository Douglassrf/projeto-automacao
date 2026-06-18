from fastapi.testclient import TestClient

from app.core.global_miner_hub import global_miner_hub_local
from app.main import app


def test_global_miner_hub_aggregates_local_multiplatform_signals():
    result = global_miner_hub_local(
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
                    "spend": 40,
                    "leads": 8,
                    "niche": "saas",
                },
                {
                    "platform": "tiktok",
                    "country": "BR",
                    "headline": "Criativo vencedor",
                    "body": "Descubra o angulo antes de gastar.",
                    "landing_url": "https://example.com",
                    "impressions": 500,
                    "clicks": 20,
                    "spend": 20,
                    "leads": 3,
                    "niche": "infoproduto",
                },
            ]
        }
    )

    assert result["status"] == "miner_batch_ready"
    assert result["will_execute_real_action"] is False
    assert result["network_access_used"] is False
    assert result["platform_counts"]["meta"] == 1
    assert result["platform_counts"]["tiktok"] == 1
    assert result["radar"]["status"] == "radar_ready"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_global_miner_hub_reports_blocked_signals():
    result = global_miner_hub_local({"signals": [{"platform": "unknown", "body": ""}]})

    assert result["status"] == "insufficient_data"
    assert result["signals_accepted"] == 0
    assert result["signals_blocked"] == 1
    assert "unsupported_platform" in result["blocked_reasons"]


def test_global_miner_hub_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/miner-hub-local",
            json={"signals": [{"platform": "meta", "headline": "Teste", "body": "Texto bom para teste", "impressions": 10}]},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37K"
