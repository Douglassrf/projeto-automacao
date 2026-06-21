from fastapi.testclient import TestClient

from app.core.api_gateway import api_gateway_guard
from app.core.rate_limit import InMemoryRateLimiter, RateLimitRule, RateLimitScope
from app.main import app


def test_cors_allows_origin_from_allowlist():
    client = TestClient(app)

    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_blocks_origin_outside_allowlist():
    client = TestClient(app)

    response = client.options(
        "/",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_http_rate_limit_returns_429_with_retry_after_when_exceeded():
    previous_limiter = api_gateway_guard.limiter
    previous_enabled = api_gateway_guard.enabled
    api_gateway_guard.enabled = True
    api_gateway_guard.limiter = InMemoryRateLimiter(
        {
            "agent_internal": RateLimitRule(
                "agent_internal",
                limit=1,
                window_seconds=60,
                scope=RateLimitScope.AGENT,
            )
        }
    )
    client = TestClient(app)

    try:
        first = client.get("/", headers={"User-Agent": "m01a-regression", "X-Actor": "m01a-test"})
        blocked = client.get("/", headers={"User-Agent": "m01a-regression", "X-Actor": "m01a-test"})
    finally:
        api_gateway_guard.limiter = previous_limiter
        api_gateway_guard.enabled = previous_enabled

    assert first.status_code == 200
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"].isdigit()
    assert blocked.json()["detail"] == "Rate limit excedido."
