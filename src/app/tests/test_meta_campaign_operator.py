from fastapi.testclient import TestClient

from app.main import app


def _payload(mode="dry_run"):
    return {
        "product_name": "Produto V3 Teste",
        "pixel_id": "1234567890",
        "landing_page_url": "https://checkout.exemplo.com/produto",
        "affiliate_id": "aff-op",
        "geo_preset": "LATAM_ESP",
        "language": "Spanish_All",
        "daily_budget_brl": 25,
        "mode": mode,
        "creatives": [
            {"name": "AD01", "media_type": "image", "copy": "Compra ahora este método práctico."},
            {"name": "AD02", "media_type": "image", "copy": "Descubre cómo resolver este problema hoy."},
            {"name": "AD03", "media_type": "video", "copy": "Mira el paso a paso antes de salir."},
            {"name": "AD04", "media_type": "video", "copy": "Accede al contenido completo ahora."},
        ],
    }


def test_campaign_operator_status():
    with TestClient(app) as client:
        response = client.get("/api/v1/campaign-operator/status")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert "LATAM_ESP" in data["supported_presets"]


def test_campaign_operator_v3_dry_run_generates_one_campaign_per_creative():
    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-operator/v3/launch", json=_payload())
    assert response.status_code == 200
    data = response.json()
    assert data["operator"] == "Meta AI Campaign Operator"
    assert data["attempted"] == 4
    assert data["dry_run"] is True
    assert len(data["results"]) == 4
    assert data["results"][0]["campaign_name"].endswith("V3 AD01")
    assert any(item["name"] == "purchase_event" and item["status"] == "ok" for item in data["guardrails"])


def test_campaign_operator_blocks_publish_without_autopublish_flag():
    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-operator/v3/launch", json=_payload(mode="publish_active"))
    assert response.status_code == 200
    data = response.json()
    assert data["blocked"] == 4
    assert any(item["name"] == "autopublish" and item["status"] == "blocked" for item in data["guardrails"])


def test_campaign_operator_reuses_existing_campaign_for_single_creative():
    payload = _payload(mode="dry_run")
    payload["existing_campaign_id"] = "52616252576068"
    payload["creatives"] = payload["creatives"][:1]

    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-operator/v3/launch", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["meta_campaign_id"] == "52616252576068"
    assert any(item["name"] == "existing_campaign_scope" and item["status"] == "ok" for item in data["guardrails"])


def test_campaign_operator_blocks_existing_campaign_with_multiple_creatives():
    payload = _payload(mode="dry_run")
    payload["existing_campaign_id"] = "52616252576068"

    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-operator/v3/launch", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["blocked"] == 4
    assert any(item["name"] == "existing_campaign_scope" and item["status"] == "blocked" for item in data["guardrails"])
