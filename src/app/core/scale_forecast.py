from __future__ import annotations

from typing import Any

from app.core.saturation_monitor import saturation_monitor_local
from app.core.winning_ad_score import winning_ad_score
from app.services.campaign_brain import CampaignBrainAgent


def scale_forecast_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    blocked: list[str] = []
    if bool(payload.get("apply_budget_change")):
        blocked.append("budget_change_forbidden_in_forecast")
    if bool(payload.get("create_scale_action")):
        blocked.append("scale_action_creation_forbidden_in_forecast")
    if bool(payload.get("call_meta_api")):
        blocked.append("meta_api_call_forbidden_in_forecast")

    score = winning_ad_score(payload)
    saturation = saturation_monitor_local(payload)
    blocked.extend(saturation["blocked_reasons"])
    if score["status"] == "blocked":
        blocked.extend(score["blocked_reasons"])

    global_score = score["score"]["global_score"] if score.get("score") else 0
    saturation_score = saturation["saturation"]["score"]
    current_budget = float(payload.get("current_budget_brl") or payload.get("daily_budget_brl") or 5)
    max_safe_increment = float(payload.get("max_safe_increment_percent") or 20)
    forecast_score = max(0, min(100, round(global_score * 0.72 - saturation_score * 0.35 + 20, 2)))

    if blocked:
        verdict = "blocked"
    elif forecast_score >= 75 and saturation["saturation"]["risk_level"] == "low":
        verdict = "scale_review_candidate"
    elif forecast_score >= 55:
        verdict = "test_more_before_scale"
    else:
        verdict = "hold"

    proposed_budget = round(current_budget * (1 + max_safe_increment / 100), 2) if verdict == "scale_review_candidate" else current_budget
    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Scale Forecast Local",
            "niche": payload.get("niche") or "global intelligence",
            "campaign_stage": "37Z",
            "outcome": verdict,
            "lesson": "Forecast de escala deve prever aumento possivel sem aplicar orcamento, criar action ou chamar Meta API.",
            "metrics": {
                "forecast_score": forecast_score,
                "global_score": global_score,
                "saturation_score": saturation_score,
                "current_budget": current_budget,
                "proposed_budget": proposed_budget,
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37Z",
        "status": "scale_forecast_ready" if not blocked else "blocked",
        "verdict": verdict,
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "budget_change_applied": False,
        "meta_api_called": False,
        "forecast": {
            "score": forecast_score,
            "current_budget_brl": current_budget,
            "proposed_review_budget_brl": proposed_budget,
            "max_safe_increment_percent": max_safe_increment,
            "global_score": global_score,
            "saturation_score": saturation_score,
            "saturation_risk": saturation["saturation"]["risk_level"],
        },
        "source_modules": {
            "winning_ad_score": score["mission"],
            "saturation_monitor": saturation["mission"],
        },
        "blocked_reasons": sorted(set(blocked)),
        "human_approval_required": True,
        "recommended_next_step": "revisar forecast com humano; escala real continua bloqueada",
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
