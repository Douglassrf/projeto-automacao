from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

_logger = logging.getLogger("adintelligence.upload_security")

try:
    import magic  # type: ignore
except Exception:  # pragma: no cover - fallback for systems without libmagic
    magic = None

try:
    from werkzeug.utils import secure_filename as werkzeug_secure_filename
except Exception:  # pragma: no cover
    werkzeug_secure_filename = None


ALLOWED_EXTENSIONS = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
}

BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".com", ".msi", ".scr",
    ".sh", ".bash", ".zsh", ".ps1",
    ".php", ".phtml", ".asp", ".aspx", ".jsp",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".py", ".rb", ".pl", ".cgi", ".jar",
    ".html", ".htm", ".svg", ".xml",
}

DANGEROUS_SIGNATURES = (
    b"MZ",                 # Windows PE executables
    b"#!",                 # shell/python scripts
    b"<?php",              # PHP
    b"<script",            # JS/HTML script
    b"<!doctype html",     # HTML
    b"<html",              # HTML
    b"%PDF-" + b"\n<script",  # defensive marker; true PDF check happens separately
)


class UploadSecurityError(ValueError):
    """Raised when an uploaded file violates a security rule."""


@dataclass(frozen=True)
class StoredUpload:
    original_filename: str
    safe_original_filename: str
    stored_filename: str
    path: str
    size_bytes: int
    detected_mime: str


def secure_user_filename(filename: str) -> str:
    cleaned = os.path.basename(filename or "upload")
    if werkzeug_secure_filename:
        cleaned = werkzeug_secure_filename(cleaned)
    else:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", cleaned).strip("._")
    return cleaned or "upload"


def extension_for(filename: str) -> str:
    return Path(filename).suffix.lower()


def detect_mime(content: bytes) -> str:
    if magic is not None:
        try:
            return magic.from_buffer(content, mime=True) or "application/octet-stream"
        except Exception:
            pass
    # Fallback based on strong magic bytes. This is not the primary path when python-magic is available.
    head = content[:32].lower()
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith((b"<script", b"<?php", b"<!doctype html", b"<html")):
        return "text/html"
    if content.startswith(b"MZ"):
        return "application/x-dosexec"
    return "application/octet-stream"


def has_valid_magic_bytes(content: bytes, expected_mime: str) -> bool:
    if expected_mime == "application/pdf":
        return content.startswith(b"%PDF-") and b"%%EOF" in content[-2048:]
    if expected_mime == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if expected_mime == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff") and content.rstrip().endswith(b"\xff\xd9")
    if expected_mime == "image/gif":
        return content.startswith((b"GIF87a", b"GIF89a"))
    if expected_mime == "image/webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return False


def looks_dangerous(content: bytes) -> bool:
    normalized = content[:512].lstrip().lower()
    return any(normalized.startswith(sig.lower()) for sig in DANGEROUS_SIGNATURES)


def validate_upload(filename: str, content: bytes, max_size_bytes: int) -> tuple[str, str, str]:
    if not content:
        raise UploadSecurityError("Arquivo vazio não é permitido.")

    if len(content) > max_size_bytes:
        raise UploadSecurityError(f"Arquivo excede o limite de {max_size_bytes} bytes.")

    safe_name = secure_user_filename(filename)
    ext = extension_for(safe_name)

    if ext in BLOCKED_EXTENSIONS:
        raise UploadSecurityError("Extensão executável ou perigosa bloqueada.")

    if ext not in ALLOWED_EXTENSIONS:
        raise UploadSecurityError("Extensão não permitida. Envie apenas PDF ou imagem válida.")

    if looks_dangerous(content):
        raise UploadSecurityError("Conteúdo com assinatura de script/executável bloqueado.")

    detected_mime = detect_mime(content)
    expected_mimes = ALLOWED_EXTENSIONS[ext]

    if detected_mime not in expected_mimes:
        raise UploadSecurityError(
            f"MIME Type incompatível: extensão {ext}, detectado {detected_mime}."
        )

    if not has_valid_magic_bytes(content, detected_mime):
        raise UploadSecurityError("Cabeçalho/assinatura do arquivo inválido.")

    return safe_name, ext, detected_mime


def _resolve_writable_upload_dir(upload_dir: str) -> Path:
    """Resolve UPLOAD_DIR com fallback seguro se o caminho configurado nao for gravavel.

    BUGFIX (homologacao real / Etapa 1): o default de UPLOAD_DIR e "/data/uploads",
    que nao existe e nao e gravavel em ambientes serverless (Vercel) nem neste
    sandbox de testes (PermissionError: [Errno 13] Permission denied: '/data').
    O comportamento anterior deixava esse erro estourar sem tratamento (500 na
    rota de upload). Este fallback segue o mesmo padrao ja usado em
    app.core.config.safe_project_path: tenta o diretorio configurado primeiro
    (respeita UPLOAD_DIR se o operador configurou algo gravavel de verdade) e,
    se falhar, cai para um diretorio gravavel dentro do projeto.
    """
    configured = Path(upload_dir).expanduser().resolve()
    try:
        configured.mkdir(parents=True, exist_ok=True)
        probe = configured / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return configured
    except OSError as exc:
        fallback = Path(__file__).resolve().parents[3] / "data" / "uploads_fallback"
        fallback.mkdir(parents=True, exist_ok=True)
        _logger.warning(
            "upload_dir_fallback_used",
            extra={"configured_dir": str(configured), "fallback_dir": str(fallback), "reason": str(exc)},
        )
        return fallback


def store_upload(filename: str, content: bytes, upload_dir: str, max_size_bytes: int) -> StoredUpload:
    safe_name, ext, detected_mime = validate_upload(filename, content, max_size_bytes)
    destination_dir = _resolve_writable_upload_dir(upload_dir)

    stored_filename = f"{uuid4().hex}{ext}"
    destination_path = (destination_dir / stored_filename).resolve()

    if destination_dir not in destination_path.parents:
        raise UploadSecurityError("Tentativa de path traversal bloqueada.")

    destination_path.write_bytes(content)

    return StoredUpload(
        original_filename=filename,
        safe_original_filename=safe_name,
        stored_filename=stored_filename,
        path=str(destination_path),
        size_bytes=len(content),
        detected_mime=detected_mime,
    )
