from datetime import UTC, datetime, timedelta

import pytest

from app.core.rate_limit import DEFAULT_RATE_LIMIT_RULES, InMemoryRateLimiter, RateLimitDecision


def test_login_rate_limit_blocks_after_five_attempts():
    limiter = InMemoryRateLimiter()
    now = datetime(2026, 6, 5, tzinfo=UTC)
    result = None

    for _ in range(5):
        result = limiter.check("login", "127.0.0.1", now=now)
        assert result.allowed

    blocked = limiter.check("login", "127.0.0.1", now=now)

    assert result is not None
    assert result.remaining == 0
    assert blocked.decision == RateLimitDecision.BLOCK
    assert blocked.reason == "rate_limit_exceeded"


def test_rate_limit_resets_after_window():
    limiter = InMemoryRateLimiter()
    now = datetime(2026, 6, 5, tzinfo=UTC)
    for _ in range(5):
        limiter.check("login", "127.0.0.1", now=now)

    later = now + timedelta(minutes=16)
    result = limiter.check("login", "127.0.0.1", now=later)

    assert result.allowed
    assert result.remaining == 4


def test_different_identifiers_have_separate_buckets():
    limiter = InMemoryRateLimiter()
    now = datetime(2026, 6, 5, tzinfo=UTC)

    for _ in range(5):
        limiter.check("login", "127.0.0.1", now=now)

    other = limiter.check("login", "10.0.0.1", now=now)

    assert other.allowed
    assert other.remaining == 4


def test_sensitive_command_limit_uses_user_scope():
    limiter = InMemoryRateLimiter()
    now = datetime(2026, 6, 5, tzinfo=UTC)

    result = limiter.check("sensitive_command", "operator@example.com", now=now)

    assert result.allowed
    assert result.key.startswith("user:sensitive_command:")


def test_unknown_rule_is_rejected():
    limiter = InMemoryRateLimiter()

    with pytest.raises(KeyError):
        limiter.check("unknown", "x")


def test_default_rules_cover_security_hardening_needs():
    assert {"login", "sensitive_command", "ai_heavy", "meta_api", "agent_internal"}.issubset(DEFAULT_RATE_LIMIT_RULES)
