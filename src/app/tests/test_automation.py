from fastapi.testclient import TestClient
from app.main import app


def test_process_feed_applies_affiliate_only_to_winners():
    payload = {
        "threshold_min": 15,
        "threshold_max": 40,
        "affiliate": {"network": "generic", "user_affiliate_id": "auto-123"},
        "items": [
            {
                "external_id": "a1",
                "product_name": "Produto Vencedor",
                "creative_original": "Oferta validada: https://checkout.exemplo.com/vencedor",
                "destination_url": "https://checkout.exemplo.com/vencedor",
                "active_ads": 18,
                "cpc": 1.0,
                "link_clicks": 100,
                "landing_page_views": 80,
                "checkout_starts": 30,
                "purchases": 5,
            },
            {
                "external_id": "a2",
                "product_name": "Produto Fraco",
                "creative_original": "Oferta teste: https://checkout.exemplo.com/fraco",
                "destination_url": "https://checkout.exemplo.com/fraco",
                "active_ads": 9,
                "cpc": 1.0,
                "link_clicks": 100,
                "landing_page_views": 70,
                "checkout_starts": 10,
                "purchases": 1,
            },
        ],
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/automation/process-feed", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["total_received"] == 2
    assert data["analyzed"] == 2
    assert data["winners"] == 1
    assert data["optimized"] == 1
    assert data["rejected"] == 1
    assert data["results"][0]["decision"] == "winner"
    assert data["results"][0]["affiliate"] is not None
    assert "aff_id=auto-123" in data["results"][0]["affiliate"]["affiliate_link"]
    assert data["results"][1]["decision"] == "rejected"
    assert data["results"][1]["affiliate"] is None
