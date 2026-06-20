from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.immutable_audit import ImmutableAuditLog
from app.main import app
from app.services import observability
from app.services.video_pipeline import VideoRenderPipeline


def _payload(**overrides):
    payload = {
        "product_name": "Produto Video Guard C03",
        "model": "V2",
        "hook": "Descubra o método seguro hoje",
        "script": "Este vídeo valida o guard de segurança antes de qualquer render pesado.",
        "cta": "Acesse agora",
        "voice_provider": "fallback",
        "scene_provider": "ffmpeg_local",
        "duration_seconds": 4,
    }
    payload.update(overrides)
    return payload


def _block_network(monkeypatch):
    def forbidden(*args, **kwargs):  # pragma: no cover - only runs on violation
        raise AssertionError("C03 tripwire: chamada de rede real bloqueada")

    monkeypatch.setattr(httpx, "get", forbidden)
    monkeypatch.setattr(httpx, "post", forbidden)
    monkeypatch.setattr(httpx, "delete", forbidden)


def test_c03_payload_normal_ffmpeg_local_continua_funcionando(tmp_path, monkeypatch):
    _block_network(monkeypatch)

    def local_scene_stub(self, payload, scene_file, audio_file, final_file, duration, warnings):
        scene_file.write_bytes(b"c03-scene-stub")
        final_file.write_bytes(b"c03-final-mp4-stub")

    monkeypatch.setattr(VideoRenderPipeline, "_render_scene_with_ffmpeg", local_scene_stub)
    settings = get_settings()
    previous = settings.kit_output_dir
    settings.kit_output_dir = str(tmp_path / "kits")
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/video/render", json=_payload())
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "created"
        assert data["provider"] == "fallback_local_silent_wav"
        assert Path(data["final_mp4"]).exists()
        assert Path(data["script_file"]).exists()
    finally:
        settings.kit_output_dir = previous


def test_c03_payload_bloqueado_retorna_403_e_nao_gera_arquivos(tmp_path, monkeypatch):
    _block_network(monkeypatch)
    settings = get_settings()
    previous = settings.kit_output_dir
    settings.kit_output_dir = str(tmp_path / "kits")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/video/render",
                json=_payload(scene_provider="huggingface_svd"),
            )
        assert response.status_code == 403, response.text
        detail = response.json()["detail"]
        assert detail["requires_human_approval"] is True
        assert "human_approval_required" in detail["blocked_reasons"]
        assert not list((tmp_path / "kits").rglob("*"))
    finally:
        settings.kit_output_dir = previous


def test_c03_tentativa_de_autoaprovacao_via_payload_extra_continua_bloqueada(tmp_path, monkeypatch):
    _block_network(monkeypatch)
    settings = get_settings()
    previous = settings.kit_output_dir
    settings.kit_output_dir = str(tmp_path / "kits")
    payload = _payload(scene_provider="huggingface_svd", confirmed_by_user=True)
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/video/render", json=payload)
        assert response.status_code == 403, response.text
        assert "human_approval_required" in response.json()["detail"]["blocked_reasons"]
        assert not list((tmp_path / "kits").rglob("*"))
    finally:
        settings.kit_output_dir = previous


def test_c03_guard_bloqueado_registra_audit_log_imutavel(monkeypatch):
    _block_network(monkeypatch)
    before = observability.immutable_audit_health()["total_events"]
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/video/render",
            json=_payload(scene_provider="huggingface_svd"),
        )
    assert response.status_code == 403, response.text

    audit_path = Path(observability.immutable_audit_health()["immutable_audit_file"])
    verification = ImmutableAuditLog(audit_path).verify()
    assert verification.ok is True
    assert verification.total_events >= before + 1
    last_line = audit_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert "video_pipeline.render.blocked" in last_line
    assert "human_approval_required" in last_line
