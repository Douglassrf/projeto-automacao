from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_capi_ingest_and_learning_loop_generates_v4_v5_v6():
    event = {
        "event_id": "evt-test-001",
        "pixel_id": "PIXEL123",
        "campaign_id": "camp-1",
        "campaign_name": "Produto Teste V3 AD01",
        "ad_id": "ad-1",
        "ad_name": "AD01 Hook Dor",
        "creative_id": "creative-winner-1",
        "creative_name": "Criativo campeão",
        "product_name": "Produto Teste Learning",
        "geo": "LATAM_ESP",
        "language": "Spanish_All",
        "value": 120.0,
        "currency": "BRL",
        "purchase_count": 1,
        "cpa": 30.0,
        "roas": 4.0,
        "connect_rate": 86.0,
        "checkout_rate": 24.0,
        "hook": "Hook campeão de dor direta",
        "copy_text": "Copy usada no anúncio vencedor.",
        "creative_pattern": "UGC com prova visual e CTA direto",
        "final_url": "https://checkout.exemplo.com/produto",
    }
    ingest = client.post("/api/v1/learning-loop/capi/ingest", json={"events": [event], "forward_to_meta": False})
    assert ingest.status_code == 200
    assert ingest.json()["stored"] == 1

    loop = client.post("/api/v1/learning-loop/generate-variations", json={
        "product_name": "Produto Teste Learning",
        "min_roas": 1,
        "min_purchases": 1,
        "generate_versions": ["V4", "V5", "V6"],
    })
    assert loop.status_code == 200
    data = loop.json()
    assert data["total_events_used"] >= 1
    versions = {item["version"] for item in data["generated_variations"]}
    assert {"V4", "V5", "V6"}.issubset(versions)


def test_learning_loop_without_events_returns_warning():
    response = client.post("/api/v1/learning-loop/generate-variations", json={"product_name": "Produto Sem Eventos 123"})
    assert response.status_code == 200
    data = response.json()
    assert data["capi_stable"] is False
    assert data["generated_variations"] == []
    assert data["warnings"]
