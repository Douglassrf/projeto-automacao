import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services import capi_enterprise as capi_module
from app.services.capi_enterprise import CapiEnterpriseService
from app.schemas.capi_enterprise import CapiEnterpriseEvent


def _payload(event_id="purchase-001"):
    return {
        "events": [
            {
                "event_name": "Purchase",
                "event_id": event_id,
                "event_source_url": "https://example.com/checkout/success",
                "pixel_id": "123456",
                "value": 97.0,
                "currency": "BRL",
                "order_id": "ORDER-1",
                "product_name": "Produto Teste",
                "campaign_id": "cmp_1",
                "ad_id": "ad_1",
                "customer": {
                    "email": " CLIENTE@EXAMPLE.COM ",
                    "phone": "+55 (85) 99999-0000",
                    "first_name": "João",
                    "last_name": "Silva",
                    "country": "BR",
                    "client_ip_address": "127.0.0.1",
                    "client_user_agent": "pytest-agent",
                    "fbp": "fb.1.123.abc",
                },
            }
        ],
        "forward_to_meta": True,
        "dry_run": True,
    }


def test_capi_enterprise_hashes_customer_data():
    event = CapiEnterpriseEvent(**_payload()["events"][0])
    prepared = CapiEnterpriseService().prepare_event(event)
    assert prepared.event_id == "purchase-001"
    assert prepared.user_data["em"][0] != "cliente@example.com"
    assert len(prepared.user_data["em"][0]) == 64
    assert len(prepared.user_data["ph"][0]) == 64
    assert prepared.custom_data["value"] == 97.0


def test_capi_enterprise_ingest_dry_run_and_dedup(tmp_path, monkeypatch):
    capi_log = tmp_path / "capi_enterprise_events.log"
    dedup_log = tmp_path / "capi_event_ids.log"
    monkeypatch.setattr(capi_module, "CAPI_ENTERPRISE_LOG", capi_log)
    monkeypatch.setattr(capi_module, "CAPI_DEDUP_LOG", dedup_log)

    with TestClient(app) as client:
        first = client.post("/api/v1/capi-enterprise/events", json=_payload("dup-001"))
        assert first.status_code == 200
        body = first.json()
        assert body["stored"] == 1
        assert body["deduplicated"] == 0
        assert body["dry_run"] is True
        assert body["results"][0]["event_match_quality_score"] >= 80

        second = client.post("/api/v1/capi-enterprise/events", json=_payload("dup-001"))
        assert second.status_code == 200
        body2 = second.json()
        assert body2["stored"] == 0
        assert body2["deduplicated"] == 1
        assert body2["results"][0]["status"] == "deduplicated"


def test_capi_browser_pixel_payload_uses_same_event_id():
    with TestClient(app) as client:
        response = client.post("/api/v1/capi-enterprise/browser-pixel-payload", json={"event": _payload("pixel-001")["events"][0]})
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == "pixel-001"
    assert body["browser_payload"]["eventID"] == "pixel-001"
    assert body["browser_payload"]["event"] == "Purchase"


def test_capi_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/capi-enterprise/health")
    assert response.status_code == 200
    body = response.json()
    assert "recommendations" in body
