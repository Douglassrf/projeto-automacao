from fastapi.testclient import TestClient
from app.main import app


def test_analyze_ad():
    payload = {
        "product_name": "Ebook Teste",
        "active_ads": 20,
        "cpc": 1.0,
        "link_clicks": 100,
        "landing_page_views": 75,
        "checkout_starts": 25,
        "purchases": 3,
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/ads/analyze", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["connect_rate"] == 75.0
    assert data["status"] == "CAMPEÃO"
    assert data["preview_url"] == "/preview/ebook-teste"
    assert data["edited_link"].startswith("/lp/ebook-teste")


def test_replace_affiliate_link():
    payload = {
        "creative_original": "Oferta campeã: https://produto.exemplo.com/oferta",
        "network": "generic",
        "user_affiliate_id": "afiliado-123",
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/affiliate/replace-link", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["original_link"] == "https://produto.exemplo.com/oferta"
    assert "aff_id=afiliado-123" in data["affiliate_link"]
    assert data["affiliate_link"] in data["creative_updated"]
