from fastapi.testclient import TestClient

from app.main import app


def test_decision_feed_is_populated_after_analysis():
    payload = {
        "product_name": "Produto Timeline",
        "active_ads": 22,
        "cpc": 0.8,
        "link_clicks": 100,
        "landing_page_views": 60,
        "checkout_starts": 18,
        "purchases": 0,
    }

    with TestClient(app) as client:
        analyze = client.post("/api/v1/ads/analyze", json=payload)
        assert analyze.status_code == 201

        response = client.get("/api/v1/logs/decisions?limit=10")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert any(item["reason_code"] == "CONNECT_RATE_LOW" for item in data)
    assert any(item["reason_code"] == "THRESHOLD_WINNER" for item in data)
    first = data[0]
    assert {"timestamp", "campaign_id", "reason_code", "action_taken", "reasoning", "severity"}.issubset(first.keys())
