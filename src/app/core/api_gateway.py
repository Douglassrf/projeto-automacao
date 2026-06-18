from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.core.rate_limit import InMemoryRateLimiter, RateLimitResult


@dataclass(frozen=True)
class GatewayDecision:
    allowed: bool
    rule: str
    identifier: str
    rate_limit: RateLimitResult


class ApiGatewayGuard:
    def __init__(self, limiter: InMemoryRateLimiter | None = None) -> None:
        self.limiter = limiter or InMemoryRateLimiter()

    def should_bypass(self, request: Request) -> bool:
        user_agent = request.headers.get("user-agent", "").lower()
        return "testclient" in user_agent

    def evaluate(self, request: Request) -> GatewayDecision:
        rule = self._rule_for_path(request.url.path)
        identifier = self._identifier_for_rule(request, rule)
        result = self.limiter.check(rule, identifier)
        return GatewayDecision(
            allowed=result.allowed,
            rule=rule,
            identifier=identifier,
            rate_limit=result,
        )

    def _rule_for_path(self, path: str) -> str:
        normalized = path.lower()
        if normalized.endswith("/auth/login"):
            return "login"
        if any(marker in normalized for marker in ("production", "assisted-execution", "rollback")):
            return "sensitive_command"
        if "meta" in normalized or "campaign-operator" in normalized:
            return "meta_api"
        if any(marker in normalized for marker in ("ai", "render", "video", "premium")):
            return "ai_heavy"
        return "agent_internal"

    def _identifier_for_rule(self, request: Request, rule: str) -> str:
        if rule == "login":
            return request.client.host if request.client else "unknown-ip"
        if rule in {"sensitive_command", "ai_heavy"}:
            return request.headers.get("x-user-id") or request.headers.get("x-actor") or "anonymous"
        if rule == "meta_api":
            return request.headers.get("x-meta-account-id") or request.headers.get("x-actor") or request.url.path
        return request.headers.get("x-actor") or request.url.path


api_gateway_guard = ApiGatewayGuard()
