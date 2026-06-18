from __future__ import annotations

from typing import Any

from app.core.global_opportunity_brief import global_opportunity_brief
from app.services.campaign_brain import CampaignBrainAgent


SUPPORTED_ACTIONS = {"prepare_campaign", "prepare_creative_review", "prepare_landing_review"}
SUPPORTED_PLATFORMS = {"meta", "google", "tiktok", "linkedin", "pinterest"}


def global_operator_dry_run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    action = str(payload.get("action") or "prepare_campaign")
    platform = str(payload.get("platform") or "meta").lower()
    daily_budget = float(payload.get("daily_budget_brl") or payload.get("daily_budget") or 5)
    brief = global_opportunity_brief(payload)
    blocked = list(brief["blockers"])

    if action not in SUPPORTED_ACTIONS:
        blocked.append("unsupported_operator_action")
    if platform not in SUPPORTED_PLATFORMS:
        blocked.append("unsupported_platform")
    if daily_budget <= 0:
        blocked.append("daily_budget_required")
    if daily_budget > 5:
        blocked.append("dry_run_budget_above_initial_limit")
    if brief["status"] != "sandbox_review_ready":
        blocked.append("brief_not_ready_for_operator")

    plan = {
        "platform": platform,
        "action": action,
        "campaign_status": "PAUSED",
        "daily_budget_brl": min(daily_budget, 5),
        "objective": "LEAD",
        "will_create_real_campaign": False,
        "will_activate_spend": False,
        "requires_human_approval": True,
        "execution_mode": "dry_run_only",
    }

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Global Operator {platform}",
            "niche": brief["summary"].get("niche") or "unknown",
            "campaign_stage": "37I",
            "outcome": "operator_plan_ready" if not blocked else "blocked",
            "lesson": "Global Operator Hub deve preparar plano dry-run e nunca executar sem aprovacao humana.",
            "metrics": {
                "blocked_reasons": blocked,
                "global_score": brief["summary"].get("global_score") or 0,
                "daily_budget_brl": daily_budget,
            },
        }
    )

    return {
        "mission": "37I",
        "status": "operator_plan_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "ready_for_operator": False,
        "blocked_reasons": sorted(set(blocked)),
        "operator_plan": plan,
        "brief_summary": brief["summary"],
        "manual_gate": {
            "required": True,
            "reason": "qualquer chamada real de plataforma exige aprovacao humana e ambiente sandbox/test_account",
        },
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
