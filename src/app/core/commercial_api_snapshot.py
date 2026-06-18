from __future__ import annotations

from typing import Any

from app.core.enterprise_dashboard_snapshot import enterprise_dashboard_snapshot
from app.services.campaign_brain import CampaignBrainAgent


PLAN_LIMITS = {
    "starter": {"signals_per_day": 100, "seats": 1, "platforms": ["meta"], "exports": False},
    "growth": {"signals_per_day": 1000, "seats": 3, "platforms": ["meta", "google", "tiktok"], "exports": True},
    "enterprise": {"signals_per_day": 10000, "seats": 10, "platforms": ["meta", "google", "tiktok", "linkedin", "pinterest"], "exports": True},
}


def commercial_api_snapshot(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    plan = str(payload.get("plan") or "starter").lower()
    limits = PLAN_LIMITS.get(plan)
    blocked: list[str] = []
    if limits is None:
        blocked.append("unsupported_plan")
        limits = PLAN_LIMITS["starter"]
    dashboard = enterprise_dashboard_snapshot(payload)
    requested_platform = str(payload.get("platform") or "meta").lower()
    if requested_platform not in limits["platforms"]:
        blocked.append("platform_not_enabled_for_plan")

    public_endpoints = [
        "/api/v1/global-intelligence/enterprise-snapshot",
        "/api/v1/global-intelligence/opportunity-brief",
        "/api/v1/global-intelligence/winning-ad-score",
        "/api/v1/global-intelligence/market-radar",
    ]
    gated_endpoints = [
        "/api/v1/global-intelligence/operator-dry-run",
        "/api/v1/global-intelligence/miner-hub-local",
        "/api/v1/global-intelligence/data-moat-local",
    ]

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Commercial API {plan}",
            "niche": dashboard["operator"]["plan"]["platform"],
            "campaign_stage": "37M",
            "outcome": "commercial_snapshot_ready" if not blocked else "blocked",
            "lesson": "API comercial deve separar visao, limites e recursos sem liberar execucao real.",
            "metrics": {
                "plan": plan,
                "blocked_reasons": blocked,
                "signals_per_day": limits["signals_per_day"],
            },
        }
    )

    return {
        "mission": "37M",
        "status": "commercial_snapshot_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "billing_enabled": False,
        "plan": plan,
        "limits": limits,
        "enabled_platforms": limits["platforms"],
        "public_endpoints": public_endpoints,
        "gated_endpoints": gated_endpoints,
        "blocked_reasons": blocked,
        "dashboard_summary": {
            "readiness": dashboard["readiness"],
            "kpis": dashboard["kpis"],
            "cards": dashboard["cards"],
        },
        "commercial_rules": [
            "sem cobranca real nesta missao",
            "sem operacao real por plano comercial",
            "operator-dry-run continua exigindo aprovacao humana para qualquer passo real futuro",
        ],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
