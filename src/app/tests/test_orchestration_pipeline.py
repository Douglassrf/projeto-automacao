from pathlib import Path
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _product_payload():
    return {
        "product_name": "Orchestration Test Offer",
        "niche": "Produto digital",
        "offer_promise": "Um método simples para executar melhor",
        "target_avatar": "Afiliados iniciantes que precisam de clareza",
        "main_pain": "Muito conteúdo espalhado e pouca execução",
        "desired_transformation": "Criar campanhas organizadas com menos esforço",
        "ticket_price": 27,
        "pixel_id": "123456789",
        "landing_page_url": "https://example.com/landing",
        "checkout_url": "https://checkout.example.com/product",
        "affiliate_link": "https://checkout.example.com/product?aff=test",
        "language": "pt",
        "geo_preset": "BRAZIL",
        "countries": ["BR"],
        "excluded_countries": [],
        "platform": "Hotmart/Kiwify",
    }


def test_orchestration_plan_only_creates_json_bash_and_n8n(tmp_path):
    settings = get_settings()
    old = settings.orchestration_output_dir
    settings.orchestration_output_dir = str(tmp_path / "orchestration")
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/orchestration/run", json={"product": _product_payload(), "run_mode": "plan_only"})
    finally:
        settings.orchestration_output_dir = old
    assert response.status_code == 200
    data = response.json()
    assert Path(data["pipeline_json"]).exists()
    assert Path(data["bash_runner"]).exists()
    assert Path(data["n8n_workflow"]).exists()
    assert data["war_kit_folder"] is None
    assert any("plan_only" in warning for warning in data["warnings"])


def test_orchestration_dry_run_generates_assets(tmp_path):
    settings = get_settings()
    old_orch = settings.orchestration_output_dir
    old_sites = settings.site_output_dir
    old_kits = settings.kit_output_dir
    settings.orchestration_output_dir = str(tmp_path / "orchestration")
    settings.site_output_dir = str(tmp_path / "sites")
    settings.kit_output_dir = str(tmp_path / "kits")
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/orchestration/run", json={"product": _product_payload(), "run_mode": "dry_run", "include_video": True, "include_site": True})
    finally:
        settings.orchestration_output_dir = old_orch
        settings.site_output_dir = old_sites
        settings.kit_output_dir = old_kits
    assert response.status_code == 200
    data = response.json()
    assert data["war_kit_folder"]
    assert data["site_preview"]
    assert data["video_mp4"]
    assert Path(data["site_preview"]).exists()
    assert Path(data["video_mp4"]).exists()
    assert len(data["steps"]) >= 6


def test_orchestration_webhook_preview():
    with TestClient(app) as client:
        response = client.post("/api/v1/orchestration/webhook-preview", json={"hello": "world", "pipeline": {"ok": True}})
    assert response.status_code == 200
    assert response.json()["status"] == "received"
