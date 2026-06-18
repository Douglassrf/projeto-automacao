from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def _ads():
    return [
        {
            "source": "local_real_export",
            "ad_id": "real_like_001",
            "product_name": "Produto Miner Controlado",
            "active_ads": 34,
            "cpc": 1.2,
            "link_clicks": 1200,
            "landing_page_views": 990,
            "checkout_starts": 260,
            "purchases": 36,
        },
        {
            "source": "local_real_export",
            "ad_id": "real_like_002",
            "product_name": "Produto Miner Controlado B",
            "active_ads": 18,
            "cpc": 1.8,
            "link_clicks": 800,
            "landing_page_views": 560,
            "checkout_starts": 80,
            "purchases": 8,
        },
    ]


def test_mission28_miner_controlled_real_processes_local_source():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/miner/controlled-real",
            json={
                "product_name": "Produto Miner Controlado",
                "niche": "produto digital",
                "ads": _ads(),
                "max_ads": 2,
                "source_label": "pytest_local_export",
            },
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission_id"] == "28"
    assert data["status"] == "approved"
    assert data["mode"] == "controlled_real_local_source"
    assert data["ads_processed"] == 2
    assert data["external_calls_made"] == 0
    assert data["scraping_used"] is False
    assert data["browser_used"] is False
    assert data["selenium_used"] is False
    assert data["meta_real"] is False
    assert data["selected_candidate"]["analysis"]["score"] >= data["ranked_candidates"][1]["analysis"]["score"]
    assert Path(data["report_path"]).exists()


def test_mission28_miner_blocks_external_call_attempts():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/miner/controlled-real",
            json={
                "product_name": "Produto Miner Controlado",
                "niche": "produto digital",
                "ads": _ads(),
                "allow_external_call": True,
            },
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "blocked"
    assert data["reason"] == "External calls remain blocked in Mission 28."
    assert data["external_calls_made"] == 0
