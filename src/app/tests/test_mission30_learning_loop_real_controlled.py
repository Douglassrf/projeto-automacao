from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _event(product_name: str, suffix: str, roas: float = 4.2):
    return {
        "event_id": f"evt-m30-{suffix}-{uuid4().hex[:8]}",
        "pixel_id": "PIXEL-M30",
        "campaign_id": "camp-m30",
        "campaign_name": f"{product_name} V3",
        "ad_id": f"ad-{suffix}",
        "ad_name": f"AD {suffix}",
        "creative_id": f"creative-{suffix}",
        "creative_name": f"Criativo {suffix}",
        "product_name": product_name,
        "geo": "BR",
        "language": "pt-BR",
        "value": 150.0,
        "currency": "BRL",
        "purchase_count": 1,
        "cpa": 32.0,
        "roas": roas,
        "connect_rate": 88.0,
        "checkout_rate": 27.0,
        "hook": "Hook controlado com prova e clareza",
        "copy_text": "Copy validada em evento real controlado.",
        "creative_pattern": "Export local com prova visual e CTA claro",
        "final_url": "https://checkout.exemplo.com/produto",
    }


def test_mission30_learning_loop_real_controlled_generates_variations_without_meta_forward():
    product_name = f"Produto M30 {uuid4().hex[:8]}"
    payload = {
        "events_payload": {
            "events": [_event(product_name, "001"), _event(product_name, "002"), _event(product_name, "003")],
            "forward_to_meta": True,
        },
        "loop_payload": {
            "product_name": product_name,
            "min_roas": 1,
            "min_purchases": 1,
            "generate_versions": ["V4", "V5", "V6"],
        },
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/learning-loop/real-controlled", json=payload)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission_id"] == "30"
    assert data["status"] == "approved"
    assert data["events_stored"] == 3
    assert data["events_forwarded_to_meta"] == 0
    assert data["meta_real"] is False
    assert data["capi_forward_blocked"] is True
    assert data["capi_stable"] is True
    versions = {item["version"] for item in data["generated_variations"]}
    assert {"V4", "V5", "V6"}.issubset(versions)
