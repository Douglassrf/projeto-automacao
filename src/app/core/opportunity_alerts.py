from __future__ import annotations

from typing import Any

from app.core.executive_reports import executive_report_local
from app.core.market_radar import market_radar_local_report
from app.core.winning_ad_score import winning_ad_score
from app.services.campaign_brain import CampaignBrainAgent


def opportunity_alerts_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    blocked: list[str] = []
    if bool(payload.get("send_webhook")):
        blocked.append("webhook_delivery_forbidden_in_local_readiness")
    if bool(payload.get("send_email")):
        blocked.append("email_delivery_forbidden_in_local_readiness")
    if bool(payload.get("auto_create_campaign")):
        blocked.append("auto_campaign_creation_forbidden_in_alerts")

    radar = market_radar_local_report({"signals": payload.get("signals") or [payload]})
    score = winning_ad_score(payload)
    report = executive_report_local(payload)
    blocked.extend(report["blocked_reasons"])
    if score["status"] == "blocked":
        blocked.extend(score["blocked_reasons"])

    global_score = score["score"]["global_score"] if score.get("score") else 0
    top_heat = radar["opportunities"][0]["heat_score"] if radar["opportunities"] else 0
    alerts: list[dict[str, Any]] = []
    if top_heat >= 75:
        alerts.append(
            {
                "type": "market_heat",
                "severity": "high",
                "title": "Oportunidade quente detectada",
                "reason": f"Heat score {top_heat}",
                "human_review_required": True,
            }
        )
    if global_score >= 80:
        alerts.append(
            {
                "type": "winning_score",
                "severity": "high",
                "title": "Criativo com score forte",
                "reason": f"Global score {global_score}",
                "human_review_required": True,
            }
        )
    elif global_score >= 60:
        alerts.append(
            {
                "type": "iteration_candidate",
                "severity": "medium",
                "title": "Candidato para iteracao",
                "reason": f"Global score {global_score}",
                "human_review_required": True,
            }
        )
    if report["blocked_reasons"]:
        alerts.append(
            {
                "type": "risk_blocker",
                "severity": "critical",
                "title": "Bloqueio antes de execucao",
                "reason": ", ".join(report["blocked_reasons"][:3]),
                "human_review_required": True,
            }
        )

    alerts.sort(key=lambda item: {"critical": 0, "high": 1, "medium": 2}.get(item["severity"], 3))
    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Opportunity Alerts Local",
            "niche": payload.get("niche") or "global intelligence",
            "campaign_stage": "37X",
            "outcome": "alerts_ready" if not blocked else "blocked",
            "lesson": "Alertas de oportunidade devem priorizar decisao humana sem webhook, e-mail ou criacao automatica de campanha.",
            "metrics": {
                "alerts": len(alerts),
                "global_score": global_score,
                "top_heat": top_heat,
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37X",
        "status": "opportunity_alerts_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "external_notification_used": False,
        "auto_campaign_created": False,
        "alerts_count": len(alerts),
        "alerts": alerts[:10],
        "source_modules": {
            "market_radar": radar["mission"],
            "winning_ad_score": score["mission"],
            "executive_report": report["mission"],
        },
        "blocked_reasons": sorted(set(blocked)),
        "recommended_next_step": "revisar alertas com humano; nao executar campanha automaticamente",
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
