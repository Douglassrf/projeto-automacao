from __future__ import annotations

from app.core.rate_limit import DEFAULT_RATE_LIMIT_RULES
from app.core.security_hardening import SERVICE_ACCOUNTS, roles_matrix


def security_hardening_status() -> dict:
    return {
        "status": "active_safe_mode",
        "mode": "safe_runtime",
        "controls": {
            "rbac": True,
            "service_accounts": True,
            "command_validator": True,
            "zero_trust_internal_calls": True,
            "immutable_audit": True,
            "human_approval": True,
            "secrets_policy": True,
            "incident_response": True,
            "rate_limit": True,
            "api_gateway_guard": True,
            "route_security_guard": True,
        },
        "protected_route_groups": [
            "meta_production",
            "site_publish",
            "ai_heavy_render",
            "video_pipeline",
            "affiliate_link_change",
        ],
        "service_accounts": sorted(SERVICE_ACCOUNTS),
        "roles": roles_matrix(),
        "rate_limit_rules": {
            name: {
                "limit": rule.limit,
                "window_seconds": rule.window_seconds,
                "scope": rule.scope.value,
            }
            for name, rule in sorted(DEFAULT_RATE_LIMIT_RULES.items())
        },
        "real_execution_policy": {
            "meta_real_requires_manual_approval": True,
            "site_publish_requires_manual_approval": True,
            "paid_ai_requires_manual_approval": True,
            "default_to_dry_run": True,
        },
    }
