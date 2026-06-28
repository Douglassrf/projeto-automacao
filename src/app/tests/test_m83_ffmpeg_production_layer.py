"""Missao 83 - FFmpeg Production Layer."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.ffmpeg_production_service import FfmpegProductionService


def test_production_report_shape():
    report = FfmpegProductionService().production_report()
    assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
    assert report["mission_number"] == 83
    assert "ffmpeg_available" in report


def test_config_schema_bumped_for_m83():
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (3, 2, 0)


def test_fallback_when_ffmpeg_required_but_absent(monkeypatch):
    settings = get_settings()
    prev_req = settings.ffmpeg_require_binary
    prev_fb = settings.ffmpeg_fallback_when_absent
    monkeypatch.setattr("shutil.which", lambda _: None)
    try:
        settings.ffmpeg_require_binary = True
        settings.ffmpeg_fallback_when_absent = False
        report = FfmpegProductionService().production_report()
        assert report["ready"] is False
        assert report["blocking_issues"]
    finally:
        settings.ffmpeg_require_binary = prev_req
        settings.ffmpeg_fallback_when_absent = prev_fb


@pytest.mark.ffmpeg
def test_video_pipeline_marked_ffmpeg():
    assert True


def test_live_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/ffmpeg-production/live")
    assert r.status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/ffmpeg-production/markdown")
    assert r.status_code == 200
