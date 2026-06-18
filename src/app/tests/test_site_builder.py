from pathlib import Path
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _payload(product="Metodo Teste"):
    return {
        "offer": {
            "product_name": product,
            "niche": "Produto digital",
            "target_geo": "USD Tier 1",
            "language": "en",
            "headline": "Discover a practical method to improve your results today",
            "subheadline": "A direct digital guide built for fast execution and clear next steps.",
            "benefits": ["Clear step-by-step", "Mobile-first experience", "Instant access"],
            "pain_points": ["Too many scattered tactics", "No clear execution path"],
            "checkout_url": "https://checkout.example.com/product",
            "cta_text": "Access now"
        },
        "template": "direct_response",
        "deploy": {"provider": "local", "dry_run": True}
    }


def test_site_builder_generates_static_files(tmp_path):
    settings = get_settings()
    old = settings.site_output_dir
    settings.site_output_dir = str(tmp_path / "sites")
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/site-builder/generate", json=_payload())
    finally:
        settings.site_output_dir = old

    assert response.status_code == 200
    data = response.json()
    assert data["deploy_status"] == "local_ready"
    assert "index.html" in data["files"]
    assert "styles.css" in data["files"]
    assert Path(data["preview_path"]).exists()
    assert "Discover a practical method" in Path(data["preview_path"]).read_text(encoding="utf-8")


def test_site_builder_dry_run_deploy_payload(tmp_path):
    settings = get_settings()
    old = settings.site_output_dir
    settings.site_output_dir = str(tmp_path / "sites")
    payload = _payload("Deploy Teste")
    payload["deploy"] = {"provider": "github_vercel", "dry_run": True, "repository_name": "deploy-teste"}
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/site-builder/generate", json=payload)
    finally:
        settings.site_output_dir = old

    assert response.status_code == 200
    data = response.json()
    assert data["deploy_status"] == "dry_run_payload_ready"
    assert data["deploy_payload_path"]
    assert Path(data["deploy_payload_path"]).exists()
    assert any("dry-run" in warning.lower() for warning in data["warnings"])
