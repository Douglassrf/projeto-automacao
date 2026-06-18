from pathlib import Path
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.main import app


def test_video_pipeline_renders_mp4_with_ffmpeg_fallback(tmp_path):
    settings = get_settings()
    previous = settings.kit_output_dir
    settings.kit_output_dir = str(tmp_path / "kits")
    payload = {
        "product_name": "Produto Video Teste",
        "model": "V2",
        "hook": "Descubra o método simples hoje",
        "script": "Este vídeo mostra uma promessa clara, uma dor forte e uma chamada direta para ação.",
        "cta": "Acesse agora",
        "voice_provider": "fallback",
        "duration_seconds": 6
    }
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/video/render", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert Path(data["final_mp4"]).exists()
        assert Path(data["audio_file"]).exists()
        assert data["provider"] == "fallback_local_silent_wav"
    finally:
        settings.kit_output_dir = previous


def test_war_kit_can_render_video_assets(tmp_path):
    settings = get_settings()
    previous = settings.kit_output_dir
    settings.kit_output_dir = str(tmp_path / "kits")
    payload = {
        "product": {
            "product_name": "Kit Video",
            "niche": "Marketing",
            "offer_promise": "criar campanhas melhores rapidamente",
            "target_avatar": "afiliados que querem validar anúncios",
            "main_pain": "falta de criativos que convertem",
            "desired_transformation": "ter um kit pronto para subir",
            "ticket_price": 47,
            "pixel_id": "123456",
            "landing_page_url": "https://example.com/page",
            "language": "Português",
            "geo_preset": "BRAZIL"
        },
        "mined_ads": [],
        "generate_pdf": False,
        "generate_images": False,
        "generate_videos": True,
        "generate_copies": False,
        "render_video_assets": True,
        "prepare_meta_upload": False
    }
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/war-kit/generate", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert any(item["kind"] == "video_render" for item in data["files"])
    finally:
        settings.kit_output_dir = previous
