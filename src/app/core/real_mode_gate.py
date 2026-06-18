from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.secrets_policy import SecretsPolicy
from app.core.security_status import security_hardening_status


def real_mode_readiness_gate(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    settings = get_settings()
    target = str(payload.get("target") or "meta").lower()
    approval_phrase = str(payload.get("approval_phrase") or "")
    expected_phrase = "EU APROVO MODO REAL ASSISTIDO"
    human_approved = bool(payload.get("confirmed_by_user")) and approval_phrase == expected_phrase
    blocked: list[str] = []

    if not human_approved:
        blocked.append("human_approval_required")
    if settings.kill_switch_enabled:
        blocked.append("kill_switch_enabled")
    if settings.automation_level_2_enabled:
        blocked.append("automation_level_2_not_allowed_for_gate")

    if target == "meta":
        if settings.meta_dry_run:
            blocked.append("meta_dry_run_enabled")
        if not settings.meta_require_manual_confirmation:
            blocked.append("manual_confirmation_disabled")
        if settings.meta_allow_active_launch:
            blocked.append("active_launch_not_allowed")
        if settings.meta_production_daily_spend_limit_brl > 50:
            blocked.append("daily_spend_limit_above_safe_limit")
        if not settings.meta_allow_production_real and settings.meta_env == "production":
            blocked.append("production_real_flag_missing")

    production = target in {"meta", "site", "ai"}
    secrets = SecretsPolicy().audit_mapping(
        {
            "JWT_SECRET_KEY": settings.jwt_secret_key,
            "DEFAULT_ADMIN_PASSWORD": settings.default_admin_password,
            "META_ACCESS_TOKEN": settings.meta_access_token if target == "meta" else "not-required-local",
            "META_AD_ACCOUNT_ID": settings.meta_ad_account_id if target == "meta" else "not-required-local",
            "META_PAGE_ID": settings.meta_page_id if target == "meta" else "not-required-local",
        },
        production=production,
    )
    if secrets["blocked"]:
        blocked.append("secrets_policy_blocked")

    security = security_hardening_status()
    missing_controls = [name for name, enabled in security["controls"].items() if not enabled]
    if missing_controls:
        blocked.append("security_controls_missing")

    return {
        "target": target,
        "status": "ready" if not blocked else "blocked",
        "ready_for_assisted_real_mode": not blocked,
        "blocked_reasons": blocked,
        "required_approval_phrase": expected_phrase,
        "security_controls_active": not missing_controls,
        "missing_controls": missing_controls,
        "secrets_summary": {
            "blocked": secrets["blocked"],
            "warnings": secrets["warnings"],
            "ok": secrets["ok"],
        },
        "policy": {
            "dry_run_default": True,
            "manual_confirmation_required": True,
            "active_launch_forbidden": True,
            "max_safe_daily_spend_brl": 50,
        },
    }
