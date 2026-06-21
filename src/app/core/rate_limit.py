from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
try:
    from enum import StrEnum
except ImportError:  # compat Python 3.10 (StrEnum requer 3.11+)
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class RateLimitScope(StrEnum):
    IP = "ip"
    USER = "user"
    AGENT = "agent"
    ROUTE = "route"
    ACTION = "action"


class RateLimitDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int
    scope: RateLimitScope


@dataclass(frozen=True)
class RateLimitResult:
    decision: RateLimitDecision
    key: str
    remaining: int
    reset_at: str
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.decision == RateLimitDecision.ALLOW


DEFAULT_RATE_LIMIT_RULES: dict[str, RateLimitRule] = {
    "login": RateLimitRule("login", limit=5, window_seconds=15 * 60, scope=RateLimitScope.IP),
    "sensitive_command": RateLimitRule("sensitive_command", limit=10, window_seconds=60 * 60, scope=RateLimitScope.USER),
    "ai_heavy": RateLimitRule("ai_heavy", limit=20, window_seconds=24 * 60 * 60, scope=RateLimitScope.USER),
    "meta_api": RateLimitRule("meta_api", limit=60, window_seconds=60 * 60, scope=RateLimitScope.ACTION),
    "agent_internal": RateLimitRule("agent_internal", limit=120, window_seconds=60 * 60, scope=RateLimitScope.AGENT),
}


class InMemoryRateLimiter:
    def __init__(self, rules: dict[str, RateLimitRule] | None = None) -> None:
        self.rules = rules or DEFAULT_RATE_LIMIT_RULES
        self._events: dict[str, list[datetime]] = {}

    @classmethod
    def from_settings(cls, settings) -> "InMemoryRateLimiter":
        rules = {
            "login": RateLimitRule(
                "login",
                limit=settings.rate_limit_login_limit,
                window_seconds=settings.rate_limit_login_window_seconds,
                scope=RateLimitScope.IP,
            ),
            "sensitive_command": RateLimitRule(
                "sensitive_command",
                limit=settings.rate_limit_sensitive_limit,
                window_seconds=settings.rate_limit_sensitive_window_seconds,
                scope=RateLimitScope.USER,
            ),
            "ai_heavy": RateLimitRule(
                "ai_heavy",
                limit=settings.rate_limit_ai_heavy_limit,
                window_seconds=settings.rate_limit_ai_heavy_window_seconds,
                scope=RateLimitScope.USER,
            ),
            "meta_api": RateLimitRule(
                "meta_api",
                limit=settings.rate_limit_meta_api_limit,
                window_seconds=settings.rate_limit_meta_api_window_seconds,
                scope=RateLimitScope.ACTION,
            ),
            "agent_internal": RateLimitRule(
                "agent_internal",
                limit=settings.rate_limit_default_limit,
                window_seconds=settings.rate_limit_default_window_seconds,
                scope=RateLimitScope.AGENT,
            ),
        }
        return cls(rules)

    def check(self, rule_name: str, identifier: str, *, now: datetime | None = None) -> RateLimitResult:
        if rule_name not in self.rules:
            raise KeyError(f"Rate limit rule nao registrada: {rule_name}")
        rule = self.rules[rule_name]
        current = now or datetime.now(UTC)
        key = f"{rule.scope.value}:{rule.name}:{identifier}"
        window_start = current - timedelta(seconds=rule.window_seconds)
        events = [event for event in self._events.get(key, []) if event > window_start]

        if len(events) >= rule.limit:
            reset_at = min(events) + timedelta(seconds=rule.window_seconds)
            self._events[key] = events
            return RateLimitResult(
                decision=RateLimitDecision.BLOCK,
                key=key,
                remaining=0,
                reset_at=reset_at.isoformat(),
                reason="rate_limit_exceeded",
            )

        events.append(current)
        self._events[key] = events
        reset_at = min(events) + timedelta(seconds=rule.window_seconds)
        return RateLimitResult(
            decision=RateLimitDecision.ALLOW,
            key=key,
            remaining=rule.limit - len(events),
            reset_at=reset_at.isoformat(),
        )

    def snapshot(self) -> dict[str, int]:
        return {key: len(events) for key, events in sorted(self._events.items())}

