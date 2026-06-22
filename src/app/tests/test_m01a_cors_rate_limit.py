from fastapi.testclient import TestClient

from app.core.api_gateway import api_gateway_guard
from app.core.rate_limit import InMemoryRateLimiter, RateLimitRule, RateLimitScope
from app.main import app


def test_m01a_cors_allows_configured_origin():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_m01a_cors_blocks_unknown_origin():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert "access-control-allow-origin" not in response.headers


def test_m01a_rate_limit_returns_retry_after(monkeypatch):
    rules = {
        "login": RateLimitRule("login", limit=1, window_seconds=60, scope=RateLimitScope.IP),
        "agent_internal": RateLimitRule("agent_internal", limit=120, window_seconds=60, scope=RateLimitScope.AGENT),
        "sensitive_command": RateLimitRule("sensitive_command", limit=10, window_seconds=60, scope=RateLimitScope.USER),
        "ai_heavy": RateLimitRule("ai_heavy", limit=20, window_seconds=60, scope=RateLimitScope.USER),
        "meta_api": RateLimitRule("meta_api", limit=60, window_seconds=60, scope=RateLimitScope.ACTION),
    }
    previous_limiter = api_gateway_guard.limiter
    api_gateway_guard.limiter = InMemoryRateLimiter(rules)
    monkeypatch.setattr(api_gateway_guard, "should_bypass", lambda request: False)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            first = client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "wrong"},
                headers={"user-agent": "m01a-no-bypass"},
            )
            blocked = client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "wrong"},
                headers={"user-agent": "m01a-no-bypass"},
            )
    finally:
        api_gateway_guard.limiter = previous_limiter

    assert first.status_code != 429
    assert blocked.status_code == 429
    assert blocked.json()["rule"] == "login"
    assert int(blocked.headers["Retry-After"]) >= 1
