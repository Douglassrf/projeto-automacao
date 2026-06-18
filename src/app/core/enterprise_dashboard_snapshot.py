from __future__ import annotations

from typing import Any

from app.core.global_operator_hub import global_operator_dry_run
from app.core.security_status import security_hardening_status
from app.services.campaign_brain import CampaignBrainAgent


def enterprise_dashboard_snapshot(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    operator = global_operator_dry_run(payload)
    security = security_hardening_status()
    summary = operator["brief_summary"]
    blockers = operator["blocked_reasons"]
    global_score = summary.get("global_score") or 0
    readiness = "green" if operator["status"] == "operator_plan_ready" else "yellow" if global_score >= 60 else "red"

    kpis = {
        "global_score": global_score,
        "ready_sections": summary.get("ready_sections") or 0,
        "blocked_reasons": len(blockers),
        "security_controls_active": sum(1 for enabled in security["controls"].values() if enabled),
        "protected_route_groups": len(security["protected_route_groups"]),
    }
    cards = [
        {"id": "opportunity", "label": "Opportunity", "status": readiness, "value": summary.get("winning_verdict")},
        {"id": "operator", "label": "Operator", "status": operator["status"], "value": operator["operator_plan"]["execution_mode"]},
        {"id": "security", "label": "Security", "status": security["status"], "value": "controls_active"},
        {"id": "risk", "label": "Risk", "status": "blocked" if blockers else "controlled", "value": len(blockers)},
    ]

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Enterprise Dashboard Snapshot",
            "niche": summary.get("niche") or "unknown",
            "campaign_stage": "37J",
            "outcome": readiness,
            "lesson": "Dashboard Enterprise deve consolidar KPIs, riscos e proxima acao sem executar plataformas.",
            "metrics": kpis,
        }
    )

    return {
        "mission": "37J",
        "status": "snapshot_ready",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "readiness": readiness,
        "kpis": kpis,
        "cards": cards,
        "operator": {
            "status": operator["status"],
            "plan": operator["operator_plan"],
            "manual_gate": operator["manual_gate"],
        },
        "security": {
            "status": security["status"],
            "controls": security["controls"],
            "protected_route_groups": security["protected_route_groups"],
        },
        "blockers": blockers,
        "recommended_next_step": "corrigir bloqueios antes de sandbox" if blockers else "revisar snapshot com humano antes de sandbox pausado",
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
