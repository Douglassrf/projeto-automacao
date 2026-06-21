import json
import logging

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.repositories.user_repository import UserRepository
from app.services import observability


def _auth_headers(email: str = "m06a.observability@example.com") -> dict[str, str]:
    db = SessionLocal()
    try:
        repo = UserRepository(db)
        user = repo.get_by_email(email)
        if user is None:
            user = repo.create(name="M06A Observability", email=email, hashed_password=hash_password("SenhaM06A!"))
        token = create_access_token(str(user.id), extra={"email": user.email})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_m06a_structured_logging_uses_json_and_configurable_level(monkeypatch):
    observability._INITIALIZED = False
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    observability.init_observability()

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    formatter = root.handlers[0].formatter
    record = logging.LogRecord("m06a", logging.INFO, __file__, 1, "hello", (), None)
    record.request_id = "corr-m06a"
    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "hello"
    assert payload["request_id"] == "corr-m06a"


def test_m06a_metrics_endpoint_requires_auth_and_reports_route_latency():
    settings = get_settings()
    previous = settings.auth_required
    observability.reset_metrics()
    try:
        settings.auth_required = True
        with TestClient(app) as client:
            unauthenticated = client.get("/api/v1/observability/metrics")
            client.get("/health", headers={"x-correlation-id": "corr-metrics"})
            authenticated = client.get("/api/v1/observability/metrics", headers=_auth_headers())
    finally:
        settings.auth_required = previous

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200, authenticated.text
    data = authenticated.json()
    assert data["requests_total"] >= 1
    assert "GET /health" in data["routes"]
    assert data["routes"]["GET /health"]["requests_total"] >= 1
    assert "latency_avg_ms" in data["routes"]["GET /health"]


def test_m06a_readiness_endpoint_requires_auth_and_reuses_component_snapshot():
    settings = get_settings()
    previous = settings.auth_required
    try:
        settings.auth_required = True
        with TestClient(app) as client:
            unauthenticated = client.get("/api/v1/observability/readiness")
            authenticated = client.get("/api/v1/observability/readiness", headers=_auth_headers("m06a.ready@example.com"))
    finally:
        settings.auth_required = previous

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200, authenticated.text
    data = authenticated.json()
    assert data["status"] in {"ready", "degraded"}
    assert {"database", "queue", "audit"}.issubset(data["components"])
    assert data["components"]["database"]["status"] == "ok"
    assert data["components"]["audit"]["hash_chain_ok"] is True
    assert data["dashboard"]["agent"] == "ObservabilityAgent"
