from fastapi import Request
from starlette.datastructures import Headers, URL

from app.core.api_gateway import ApiGatewayGuard
from app.core.rate_limit import InMemoryRateLimiter, RateLimitRule, RateLimitScope


class DummyClient:
    host = "127.0.0.1"


class DummyRequest:
    def __init__(self, path: str, headers: dict[str, str] | None = None) -> None:
        self.url = URL(path=path)
        self.headers = Headers(headers or {})
        self.client = DummyClient()


def _request(path: str, headers: dict[str, str] | None = None) -> Request:
    return DummyRequest(path, headers)  # type: ignore[return-value]


def test_gateway_classifies_login_by_ip():
    guard = ApiGatewayGuard()

    decision = guard.evaluate(_request("/api/v1/auth/login"))

    assert decision.allowed is True
    assert decision.rule == "login"
    assert decision.identifier == "127.0.0.1"


def test_gateway_blocks_after_rule_limit():
    limiter = InMemoryRateLimiter(
        {
            "login": RateLimitRule("login", limit=1, window_seconds=60, scope=RateLimitScope.IP),
            "agent_internal": RateLimitRule("agent_internal", limit=10, window_seconds=60, scope=RateLimitScope.AGENT),
        }
    )
    guard = ApiGatewayGuard(limiter)

    first = guard.evaluate(_request("/api/v1/auth/login"))
    second = guard.evaluate(_request("/api/v1/auth/login"))

    assert first.allowed is True
    assert second.allowed is False
    assert second.rate_limit.reason == "rate_limit_exceeded"


def test_gateway_classifies_sensitive_command_by_actor():
    guard = ApiGatewayGuard()

    decision = guard.evaluate(_request("/api/v1/campaign-operator/production/assisted-execution", {"x-actor": "Brian"}))

    assert decision.allowed is True
    assert decision.rule == "sensitive_command"
    assert decision.identifier == "Brian"


def test_gateway_bypasses_automated_test_client_only():
    guard = ApiGatewayGuard()

    assert guard.should_bypass(_request("/health", {"user-agent": "testclient"})) is True
    assert guard.should_bypass(_request("/health", {"user-agent": "Mozilla/5.0"})) is False
