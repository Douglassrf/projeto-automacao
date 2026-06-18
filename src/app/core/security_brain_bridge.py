from __future__ import annotations

from typing import Any

from app.core.real_mode_gate import real_mode_readiness_gate
from app.core.security_status import security_hardening_status
from app.services.campaign_brain import CampaignBrainAgent


def security_brain_review(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    target = str(payload.get("target") or "meta")
    status = security_hardening_status()
    gate = real_mode_readiness_gate(payload)
    brain = CampaignBrainAgent()
    brain_review = brain.review_before_campaign(
        {
            "product_name": f"Security Gate {target}",
            "niche": "seguranca operacional",
            "campaign_stage": "V1",
            "budget_brl": 0,
            "metrics": {
                "security_controls": sum(1 for enabled in status["controls"].values() if enabled),
                "blocked_reasons": len(gate["blocked_reasons"]),
            },
            "copy": "Revisao consultiva de seguranca antes de modo real assistido.",
        }
    )
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Security Gate {target}",
            "niche": "seguranca operacional",
            "campaign_stage": "36F",
            "outcome": gate["status"],
            "lesson": "Brain/Brian devem consultar Security Status e Real Mode Gate antes de qualquer acao sensivel.",
            "metrics": {
                "controls_active": status["controls"],
                "blocked_reasons": gate["blocked_reasons"],
            },
        }
    )
    return {
        "agent": "SecurityBrainBridge",
        "status": "ok",
        "target": target,
        "security_status": {
            "status": status["status"],
            "protected_route_groups": status["protected_route_groups"],
            "controls_active": all(status["controls"].values()),
        },
        "real_mode_gate": gate,
        "brain_review": {
            "decision": brain_review["decision"],
            "next_action": brain_review["next_action"],
            "blocked_reasons": brain_review["blocked_reasons"],
            "recommended_solution": brain_review["recommended_solution"],
        },
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
