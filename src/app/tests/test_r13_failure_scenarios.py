from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import auth as auth_route
from app.api.routes import upload as upload_route
from app.core.api_gateway import api_gateway_guard
from app.core.config import get_settings
from app.core.rate_limit import InMemoryRateLimiter, RateLimitDecision
from app.core.security import ALGORITHM, create_access_token
from app.db.init_db import init_db
from app.integrations.meta_marketing import MetaMarketingClient, MetaMarketingError
from app.main import app
from app.schemas.video_pipeline import VideoRenderRequest
from app.services.video_pipeline import VideoRenderPipeline

UTC = timezone.utc


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _settings_auth_required():
    settings = get_settings()
    settings.auth_required = True
    init_db()
    return settings


def test_r13_invalid_login_is_controlled():
    settings = _settings_auth_required()
    with _client() as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": settings.default_admin_email, "password": "wrong-password"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "E-mail ou senha inválidos."
    assert "traceback" not in response.text.lower()


def test_r13_missing_invalid_expired_and_tampered_tokens_are_controlled():
    settings = _settings_auth_required()
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    valid = create_access_token("1")
    tampered = valid[:-1] + ("a" if valid[-1] != "a" else "b")

    with _client() as client:
        missing = client.get("/api/v1/auth/me")
        malformed = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
        expired_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
        tampered_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})

    assert missing.status_code == 401
    assert missing.json()["detail"] == "Login necessário."
    for response in (malformed, expired_response, tampered_response):
        assert response.status_code == 401
        assert response.json()["detail"] == "Token inválido ou expirado."
        assert "traceback" not in response.text.lower()


def test_r13_invalid_upload_extension_magic_empty_and_large_are_controlled(tmp_path):
    settings = get_settings()
    settings.auth_required = False
    settings.upload_dir = str(tmp_path)
    settings.upload_max_bytes = 1024

    with _client() as client:
        blocked_extension = client.post(
            "/api/v1/upload",
            files={"file": ("script.sh", b"#!/bin/sh\necho blocked", "text/x-shellscript")},
        )
        bad_magic = client.post(
            "/api/v1/upload",
            files={"file": ("fake.png", b"not-a-png", "image/png")},
        )
        empty = client.post(
            "/api/v1/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        settings.upload_max_bytes = 16
        too_large = client.post(
            "/api/v1/upload",
            files={"file": ("large.pdf", b"%PDF-1.4\n" + b"A" * 32 + b"\n%%EOF", "application/pdf")},
        )

    assert blocked_extension.status_code == 400
    assert "bloqueada" in blocked_extension.json()["detail"].lower()
    assert bad_magic.status_code == 400
    assert "incompat" in bad_magic.json()["detail"].lower() or "inválido" in bad_magic.json()["detail"].lower()
    assert empty.status_code == 400
    assert "vazio" in empty.json()["detail"].lower()
    assert too_large.status_code in (400, 413)
    assert "limite" in too_large.json()["detail"].lower()
    for response in (blocked_extension, bad_magic, empty, too_large):
        assert "traceback" not in response.text.lower()


def test_r13_database_unavailable_does_not_expose_stack_trace():
    _settings_auth_required()

    def unavailable_db():
        raise SQLAlchemyError("r13 synthetic database unavailable")
        yield

    app.dependency_overrides[auth_route.get_db] = unavailable_db
    try:
        with _client() as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "irrelevant"},
            )
    finally:
        app.dependency_overrides.pop(auth_route.get_db, None)

    assert response.status_code == 500
    assert "traceback" not in response.text.lower()
    assert "r13 synthetic" not in response.text.lower()


def test_r13_meta_api_failure_uses_tripwire_without_real_network(monkeypatch):
    settings = get_settings()
    settings.meta_access_token = "test-token-placeholder"
    settings.meta_ad_account_id = "act_test_placeholder"
    client = MetaMarketingClient()

    def blocked_post(*args, **kwargs):
        raise httpx.ConnectError("R13 tripwire: network disabled")

    monkeypatch.setattr("app.integrations.meta_marketing.httpx.post", blocked_post)

    try:
        client._post("/act_test_placeholder/campaigns", {"name": "R13"})
        raised = None
    except MetaMarketingError as exc:
        raised = exc

    assert raised is not None
    assert str(raised) == "Falha de conexão com a Meta API."
    assert "test-token-placeholder" not in str(raised)


def test_r13_ffmpeg_absent_is_controlled(monkeypatch, tmp_path):
    settings = get_settings()
    settings.kit_output_dir = str(tmp_path)
    monkeypatch.setattr("app.services.video_pipeline.shutil.which", lambda name: None)
    payload = VideoRenderRequest(
        product_name="R13 FFmpeg",
        model="V2",
        hook="Hook seguro",
        script="Roteiro curto para validar falha controlada sem ffmpeg.",
        cta="Continuar",
        duration_seconds=6,
    )

    try:
        VideoRenderPipeline().render(payload)
        raised = None
    except RuntimeError as exc:
        raised = exc

    assert raised is not None
    assert str(raised) == "FFmpeg não está instalado no ambiente."


def test_r13_generic_internal_error_does_not_expose_stack_trace(monkeypatch, tmp_path):
    settings = get_settings()
    settings.auth_required = False
    settings.upload_dir = str(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("r13 synthetic internal no secret")

    monkeypatch.setattr(upload_route, "store_upload", boom)
    with _client() as client:
        response = client.post(
            "/api/v1/upload",
            files={"file": ("ok.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        )

    assert response.status_code == 500
    assert "traceback" not in response.text.lower()
    assert "r13 synthetic" not in response.text.lower()


def test_r13_rate_limit_is_implemented_and_blocks():
    limiter = InMemoryRateLimiter()
    now = datetime(2026, 6, 20, tzinfo=UTC)
    last_allowed = None
    for _ in range(5):
        last_allowed = limiter.check("login", "203.0.113.10", now=now)
    blocked = limiter.check("login", "203.0.113.10", now=now)

    assert last_allowed is not None
    assert last_allowed.allowed
    assert blocked.decision == RateLimitDecision.BLOCK
    assert blocked.reason == "rate_limit_exceeded"


def test_r13_gateway_rate_limit_http_response_is_controlled(monkeypatch):
    class NonBypassGuard:
        def should_bypass(self, request):
            return False

        def evaluate(self, request):
            return api_gateway_guard.evaluate(request)

    previous_limiter = api_gateway_guard.limiter
    api_gateway_guard.limiter = InMemoryRateLimiter()
    monkeypatch.setattr(api_gateway_guard, "should_bypass", lambda request: False)
    try:
        with _client() as client:
            responses = [
                client.post(
                    "/api/v1/auth/login",
                    json={"email": "nobody@example.com", "password": "wrong"},
                    headers={"user-agent": "r13-no-bypass"},
                )
                for _ in range(6)
            ]
    finally:
        api_gateway_guard.limiter = previous_limiter

    assert responses[-1].status_code == 429
    body = responses[-1].json()
    assert body["detail"] == "Rate limit excedido."
    assert body["rule"] == "login"
    assert "traceback" not in responses[-1].text.lower()
