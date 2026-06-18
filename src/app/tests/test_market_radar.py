from fastapi.testclient import TestClient

from app.core.market_radar import market_radar_local_report
from app.main import app


def test_market_radar_ranks_local_opportunities_without_execution():
    report = market_radar_local_report(
        {
            "signals": [
                {
                    "platform": "meta",
                    "country": "US",
                    "headline": "Better creative decisions",
                    "body": "Find ad angles before scaling.",
                    "landing_url": "https://example.com",
                    "impressions": 1000,
                    "clicks": 80,
                    "spend": 40,
                    "leads": 10,
                    "niche": "saas",
                },
                {
                    "platform": "tiktok",
                    "country": "BR",
                    "headline": "Criativo vencedor",
                    "body": "Descubra o angulo antes de gastar.",
                    "landing_url": "https://example.com",
                    "impressions": 500,
                    "clicks": 15,
                    "spend": 30,
                    "leads": 1,
                    "niche": "infoproduto",
                },
            ]
        }
    )

    assert report["status"] == "radar_ready"
    assert report["will_execute_real_action"] is False
    assert report["opportunities"][0]["niche"] == "saas"
    assert report["opportunities"][0]["heat_score"] > report["opportunities"][1]["heat_score"]
    assert report["brian_learning"]["stored"]["status"] == "stored"


def test_market_radar_reports_insufficient_data_when_all_signals_blocked():
    report = market_radar_local_report({"signals": [{"platform": "unknown"}]})

    assert report["status"] == "insufficient_data"
    assert report["signals_accepted"] == 0
    assert report["signals_blocked"] == 1


def test_market_radar_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/market-radar",
            json={"signals": [{"platform": "meta", "headline": "H", "body": "B", "impressions": 10}]},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37B"
