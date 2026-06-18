from fastapi.testclient import TestClient

from app.core.saturation_monitor import saturation_monitor_local
from app.main import app


def _payload():
    signal = {
        "platform": "meta",
        "country": "BR",
        "headline": "Oferta com criativo repetido",
        "body": "Mesmo angulo rodando por tempo suficiente para revisar fadiga.",
        "landing_url": "https://example.com",
        "impressions": 1000,
        "clicks": 40,
        "conversions": 5,
        "spend": 50,
        "niche": "affiliate",
    }
    return {
        "tenant": "Acme Ads",
        "workspace": "main",
        "plan": "growth",
        "frequency": 4.5,
        "ctr_drop_percent": 30,
        "headline": signal["headline"],
        "body": signal["body"],
        "landing_url": signal["landing_url"],
        "impressions": signal["impressions"],
        "clicks": signal["clicks"],
        "niche": signal["niche"],
        "signals": [signal, dict(signal), dict(signal)],
    }


def test_saturation_monitor_detects_duplicate_and_frequency_risk():
    result = saturation_monitor_local(_payload())

    assert result["mission"] == "37Y"
    assert result["campaign_mutation_used"] is False
    assert result["saturation"]["risk_level"] in {"medium", "high"}
    assert result["saturation"]["duplicate_count"] >= 1
    assert result["human_review_required"] is True
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_saturation_monitor_blocks_auto_mutations():
    payload = _payload()
    payload["auto_pause_campaign"] = True
    payload["auto_rotate_creatives"] = True
    result = saturation_monitor_local(payload)

    assert result["status"] == "blocked"
    assert "auto_pause_forbidden_in_saturation_readiness" in result["blocked_reasons"]
    assert "auto_rotate_creatives_forbidden_in_saturation_readiness" in result["blocked_reasons"]


def test_saturation_monitor_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/global-intelligence/saturation-monitor", json=_payload())

    assert response.status_code == 200
    assert response.json()["mission"] == "37Y"
