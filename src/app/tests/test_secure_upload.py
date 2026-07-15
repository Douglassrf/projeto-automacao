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


def test_upload_dir_writable_path_is_used_as_is(tmp_path):
    """Cenario saudavel: se o diretorio configurado existe e e gravavel, usa ele direto."""
    from app.services.upload_security import _resolve_writable_upload_dir
    resolved = _resolve_writable_upload_dir(str(tmp_path))
    assert resolved == tmp_path.resolve()


def test_upload_dir_falls_back_when_configured_path_is_not_writable():
    """Regressao (Etapa 1 - homologacao real):

    UPLOAD_DIR default e "/data/uploads", que nao existe e nao e gravavel em
    ambientes serverless (Vercel) nem no sandbox de CI. Antes desta correcao,
    store_upload() deixava o PermissionError do mkdir() estourar sem tratamento
    (500 na rota /api/v1/upload). Agora deve cair para um diretorio de fallback
    gravavel dentro do projeto, sem lancar excecao.
    """
    import os
    from app.services.upload_security import _resolve_writable_upload_dir
    resolved = _resolve_writable_upload_dir("/data/uploads_test_nao_gravavel")
    assert resolved.exists()
    assert os.access(resolved, os.W_OK)
    assert "uploads_fallback" in str(resolved)


def test_upload_endpoint_does_not_500_when_upload_dir_is_unwritable():
    """Fluxo de erro de infra (Etapa 4): diretorio indisponivel nao pode gerar 500 cru."""
    settings = get_settings()
    original_dir = settings.upload_dir
    try:
        settings.upload_dir = "/data/uploads_test_nao_gravavel"
        pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        response = client.post(
            "/api/v1/upload",
            files={"file": ("relatorio.pdf", pdf, "application/pdf")},
        )
        assert response.status_code == 201
    finally:
        settings.upload_dir = original_dir
