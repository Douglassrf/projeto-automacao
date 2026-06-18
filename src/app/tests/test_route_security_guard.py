from app.core.route_security import (
    affiliate_link_security_guard,
    ai_heavy_security_guard,
    meta_production_security_guard,
    site_publish_security_guard,
)


def test_meta_production_security_guard_blocks_without_human_approval():
    guard = meta_production_security_guard({"launch_payload": {"daily_budget_brl": 5}})

    assert guard["status"] == "blocked"
    assert "human_approval_required" in guard["blocked_reasons"]
    assert guard["requires_human_approval"] is True


def test_meta_production_security_guard_allows_approved_low_budget_request():
    guard = meta_production_security_guard(
        {
            "launch_payload": {"daily_budget_brl": 5},
            "confirmed_by_user": True,
            "rollback_policy_ack": True,
            "brain_approval_ack": True,
        }
    )

    assert guard["status"] == "ok"
    assert guard["blocked_reasons"] == []
    assert guard["command_context"]["actor"] == "ApiOperator"


def test_meta_production_security_guard_blocks_budget_above_limit():
    guard = meta_production_security_guard(
        {
            "launch_payload": {"daily_budget_brl": 500},
            "confirmed_by_user": True,
            "rollback_policy_ack": True,
            "brain_approval_ack": True,
        }
    )

    assert guard["status"] == "blocked"
    assert "budget_above_limit" in guard["blocked_reasons"]


def test_site_publish_security_guard_allows_dry_run_deploy():
    guard = site_publish_security_guard({"deploy": {"provider": "github_vercel", "dry_run": True}})

    assert guard["status"] == "ok"
    assert guard["blocked_reasons"] == []


def test_site_publish_security_guard_blocks_real_deploy_without_approval():
    guard = site_publish_security_guard({"deploy": {"provider": "vercel", "dry_run": False}})

    assert guard["status"] == "blocked"
    assert "human_approval_required" in guard["blocked_reasons"]


def test_ai_heavy_security_guard_blocks_paid_provider_without_approval():
    guard = ai_heavy_security_guard({"provider": "runway", "dry_run": False})

    assert guard["status"] == "blocked"
    assert "human_approval_required" in guard["blocked_reasons"]


def test_affiliate_link_security_guard_allows_local_rewrite():
    guard = affiliate_link_security_guard({"ad_id": 123})

    assert guard["status"] == "ok"
    assert guard["blocked_reasons"] == []
