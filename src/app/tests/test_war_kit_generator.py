from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app


def test_war_kit_generator_creates_campaign_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("KIT_OUTPUT_DIR", str(tmp_path / "kits"))
    payload = {
        "product": {
            "product_name": "Produto Teste",
            "niche": "Saúde",
            "offer_promise": "melhorar a rotina em poucos passos",
            "target_avatar": "adultos buscando uma solução simples",
            "main_pain": "falta de clareza sobre o problema",
            "desired_transformation": "ter um plano prático de ação",
            "ticket_price": 97,
            "pixel_id": "123456",
            "landing_page_url": "https://example.com/page",
            "checkout_url": "https://example.com/checkout",
            "language": "Spanish (All)",
            "geo_preset": "LATAM_ESP"
        },
        "mined_ads": [{
            "source_ad_id": "ad_001",
            "active_ads": 25,
            "hook": "Descubre el método simple",
            "creative_pattern": "UGC direto com prova visual",
            "copy_pattern": "dor + prova + CTA",
            "cta_pattern": "Comprar ahora",
            "connect_rate": 82,
            "roas": 2.5
        }],
        "prepare_meta_upload": True
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/war-kit/generate", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_files"] >= 8
    assert data["meta_ready"] is True
    kit_folder = Path(data["kit_folder"])
    assert (kit_folder / "Copies" / "V1_copy_pack.md").exists()
    assert (kit_folder / "PDFs" / "produto-teste_lead_magnet.pdf").exists()
    assert (kit_folder / "Meta_Upload" / "meta_campaign_payload.json").exists()
