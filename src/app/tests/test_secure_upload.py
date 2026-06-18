from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def override_settings(tmp_path, max_bytes=5 * 1024 * 1024):
    settings = get_settings()
    settings.upload_dir = str(tmp_path)
    settings.upload_max_bytes = max_bytes
    return settings


def test_accepts_valid_pdf(tmp_path):
    override_settings(tmp_path)
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    response = client.post(
        "/api/v1/upload",
        files={"file": ("../relatorio final.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["detected_mime"] == "application/pdf"
    assert data["stored_filename"].endswith(".pdf")
    assert ".." not in data["safe_original_filename"]
    assert len(list(Path(tmp_path).glob("*.pdf"))) == 1


def test_rejects_fake_image_with_executable_bytes(tmp_path):
    override_settings(tmp_path)
    fake = b"MZ" + b"0" * 100
    response = client.post(
        "/api/v1/upload",
        files={"file": ("malware.jpg", fake, "image/jpeg")},
    )
    assert response.status_code == 400
    assert "bloqueado" in response.json()["detail"].lower() or "incompat" in response.json()["detail"].lower()


def test_rejects_path_traversal_and_sanitizes_name(tmp_path):
    override_settings(tmp_path)
    pdf = b"%PDF-1.7\nbody\n%%EOF"
    response = client.post(
        "/api/v1/upload",
        files={"file": ("../../../../evil.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["safe_original_filename"] == "evil.pdf"


def test_rejects_file_above_limit(tmp_path):
    override_settings(tmp_path, max_bytes=16)
    pdf = b"%PDF-1.4\n" + b"A" * 100 + b"\n%%EOF"
    response = client.post(
        "/api/v1/upload",
        files={"file": ("large.pdf", pdf, "application/pdf")},
    )
    assert response.status_code in (400, 413)


def test_rejects_blocked_extension(tmp_path):
    override_settings(tmp_path)
    response = client.post(
        "/api/v1/upload",
        files={"file": ("script.sh", b"#!/bin/sh\necho pwned", "text/x-shellscript")},
    )
    assert response.status_code == 400
