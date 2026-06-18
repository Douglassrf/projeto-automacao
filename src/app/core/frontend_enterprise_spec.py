from __future__ import annotations

from typing import Any

from app.core.enterprise_dashboard_snapshot import enterprise_dashboard_snapshot
from app.core.public_api_readiness import public_api_readiness
from app.services.campaign_brain import CampaignBrainAgent


def frontend_enterprise_spec(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    snapshot = enterprise_dashboard_snapshot(payload)
    public_api = public_api_readiness(payload)
    screens = [
        {"id": "command_center", "title": "Command Center", "widgets": ["kpi_strip", "risk_cards", "next_action"], "scope": "dashboard.read"},
        {"id": "market_radar", "title": "Market Radar", "widgets": ["opportunity_table", "country_filter", "platform_filter"], "scope": "radar.read"},
        {"id": "ad_score", "title": "Winning Ad Score", "widgets": ["score_breakdown", "verdict", "revision_queue"], "scope": "score.read"},
        {"id": "operator", "title": "Operator Dry Run", "widgets": ["paused_plan", "manual_gate", "blockers"], "scope": "operator.prepare"},
        {"id": "security", "title": "Security", "widgets": ["controls", "route_groups", "audit_status"], "scope": "security.read"},
    ]
    filters = ["tenant", "workspace", "country", "platform", "niche", "plan", "readiness"]
    blocked = list(public_api["blocked_reasons"])
    if snapshot["status"] != "snapshot_ready":
        blocked.append("dashboard_snapshot_not_ready")

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Frontend Enterprise Spec",
            "niche": public_api["tenant"]["name"],
            "campaign_stage": "37Q",
            "outcome": "frontend_spec_ready" if not blocked else "blocked",
            "lesson": "Frontend enterprise deve consumir snapshots seguros e manter execucao real fora da UI.",
            "metrics": {
                "screens": len(screens),
                "filters": len(filters),
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37Q",
        "status": "frontend_spec_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "frontend_built": False,
        "screens": screens,
        "global_filters": filters,
        "design_rules": [
            "interface densa e operacional",
            "cards apenas para itens individuais",
            "acoes reais sempre bloqueadas atras de manual gate",
            "nunca exibir segredo, token ou valor sensivel",
        ],
        "data_sources": {
            "enterprise_snapshot": "/api/v1/global-intelligence/enterprise-snapshot",
            "public_api_readiness": "/api/v1/global-intelligence/public-api-readiness",
            "operator_dry_run": "/api/v1/global-intelligence/operator-dry-run",
        },
        "preview": {
            "readiness": snapshot["readiness"],
            "cards": snapshot["cards"],
            "kpis": snapshot["kpis"],
        },
        "blocked_reasons": sorted(set(blocked)),
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
