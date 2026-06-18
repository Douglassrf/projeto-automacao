from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _make_png(path: Path):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x320:d=0.1", "-frames:v", "1", str(path)
    ], check=True, capture_output=True)


def _make_mp4(path: Path):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x568:d=1", "-pix_fmt", "yuv420p", str(path)
    ], check=True, capture_output=True)


def test_process_ugc_image(tmp_path):
    settings = get_settings()
    previous_dir = settings.ugc_output_dir
    settings.ugc_output_dir = str(tmp_path / "ugc")
    png_path = tmp_path / "criativo.png"
    _make_png(png_path)

    client = TestClient(app)
    with png_path.open("rb") as file:
        response = client.post(
            "/api/v1/ugc/process",
            files={"file": ("criativo.png", file, "image/png")},
            data={"target_preset": "feed_image"},
        )

    settings.ugc_output_dir = previous_dir
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "processed"
    assert data["media_type"] == "image"
    assert data["processed_path"].endswith("_optimized.jpg")
    assert Path(data["processed_path"]).exists()


def test_process_ugc_video(tmp_path):
    settings = get_settings()
    previous_dir = settings.ugc_output_dir
    settings.ugc_output_dir = str(tmp_path / "ugc")
    video_path = tmp_path / "ugc-video.mp4"
    _make_mp4(video_path)

    client = TestClient(app)
    with video_path.open("rb") as file:
        response = client.post(
            "/api/v1/ugc/process",
            files={"file": ("ugc-video.mp4", file, "video/mp4")},
            data={"target_preset": "reels_9_16"},
        )

    settings.ugc_output_dir = previous_dir
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "processed"
    assert data["media_type"] == "video"
    assert data["processed_path"].endswith("_optimized.mp4")
    assert Path(data["processed_path"]).exists()


def test_process_ugc_blocks_dangerous_extension(tmp_path):
    client = TestClient(app)
    response = client.post(
        "/api/v1/ugc/process",
        files={"file": ("hack.sh", b"#!/bin/bash\necho pwn", "text/x-shellscript")},
        data={"target_preset": "social_ad"},
    )
    assert response.status_code == 400
    assert "perigosa" in response.json()["detail"].lower()
