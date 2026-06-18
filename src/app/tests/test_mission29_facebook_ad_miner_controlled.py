from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def _local_export_ads():
    return [
        {
            "source": "manual_ad_library_export",
            "ad_id": "fb_real_like_001",
            "product_name": "Produto FB Miner",
            "niche": "produto digital",
            "creative_angle": "oferta direta controlada",
            "hook": "Veja o metodo pratico hoje",
            "active_ads": 41,
            "cpc": 1.05,
            "link_clicks": 1800,
            "landing_page_views": 1510,
            "checkout_starts": 420,
            "purchases": 55,
            "country": "BR",
            "language": "pt-BR",
            "risk_notes": ["validar promessa", "sem alegacao absoluta"],
        },
        {
            "source": "manual_ad_library_export",
            "ad_id": "fb_real_like_002",
            "product_name": "Produto FB Miner B",
            "niche": "produto digital",
            "creative_angle": "prova e rotina",
            "hook": "Organize sua execucao com clareza",
            "active_ads": 23,
            "cpc": 1.42,
            "link_clicks": 1000,
            "landing_page_views": 760,
            "checkout_starts": 150,
            "purchases": 18,
            "country": "BR",
            "language": "pt-BR",
        },
    ]


def test_mission29_facebook_ad_miner_collects_local_export_only():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/facebook-ad-miner/controlled-real",
            json={
                "product_name": "Produto FB Miner",
                "niche": "produto digital",
                "ads": _local_export_ads(),
                "max_ads": 2,
                "source_label": "pytest_manual_export",
            },
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission_id"] == "29"
    assert data["status"] == "approved"
    assert data["mode"] == "controlled_real_local_export"
    assert data["ads_collected"] == 2
    assert data["external_calls_made"] == 0
    assert data["scraping_used"] is False
    assert data["browser_used"] is False
    assert data["selenium_used"] is False
    assert data["meta_real"] is False
    assert data["selected_candidate"]["ad_id"] == "fb_real_like_001"
    assert Path(data["report_path"]).exists()


def test_mission29_facebook_ad_miner_blocks_external_collection_attempt():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/facebook-ad-miner/controlled-real",
            json={
                "product_name": "Produto FB Miner",
                "niche": "produto digital",
                "ads": _local_export_ads(),
                "allow_external_call": True,
                "use_browser": True,
                "source_url": "https://www.facebook.com/ads/library/",
            },
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "blocked"
    assert "external_call_blocked" in data["blocked_reasons"]
    assert "browser_blocked" in data["blocked_reasons"]
    assert "source_url_blocked_until_manual_approval" in data["blocked_reasons"]
    assert data["external_calls_made"] == 0
