from __future__ import annotations

from typing import Any

from app.core.data_moat import data_moat_local_snapshot
from app.core.opportunity_alerts import opportunity_alerts_local
from app.services.campaign_brain import CampaignBrainAgent


def saturation_monitor_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    blocked: list[str] = []
    if bool(payload.get("auto_pause_campaign")):
        blocked.append("auto_pause_forbidden_in_saturation_readiness")
    if bool(payload.get("auto_rotate_creatives")):
        blocked.append("auto_rotate_creatives_forbidden_in_saturation_readiness")

    moat = data_moat_local_snapshot(payload)
    alerts = opportunity_alerts_local(payload)
    blocked.extend(alerts["blocked_reasons"])
    signals_received = moat["miner_summary"]["signals_received"]
    duplicate_rate = round(moat["duplicate_count"] / signals_received, 4) if signals_received else 0.0
    frequency = float(payload.get("frequency") or payload.get("avg_frequency") or 0)
    ctr_drop_percent = float(payload.get("ctr_drop_percent") or payload.get("ctr_drop") or 0)
    saturation_score = min(
        100,
        round(duplicate_rate * 45 + max(0, frequency - 2) * 15 + max(0, ctr_drop_percent) * 1.2 + moat["duplicate_count"] * 8, 2),
    )
    risk_level = "high" if saturation_score >= 70 else "medium" if saturation_score >= 35 else "low"
    recommendations = [
        "criar novas variacoes de headline e hook" if risk_level != "low" else "manter monitoramento leve",
        "reduzir escala ate revisar fadiga" if risk_level == "high" else "validar proxima amostra antes de escalar",
        "comparar por plataforma, pais e nicho antes de qualquer acao real",
    ]

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Saturation Monitor Local",
            "niche": next(iter(moat["niche_counts"]), "sem sinal") if moat["niche_counts"] else "sem sinal",
            "campaign_stage": "37Y",
            "outcome": "saturation_ready" if not blocked else "blocked",
            "lesson": "Monitor de saturacao deve detectar fadiga por duplicidade, frequencia e queda de CTR sem pausar ou rotacionar campanhas automaticamente.",
            "metrics": {
                "saturation_score": saturation_score,
                "risk_level": risk_level,
                "duplicate_rate": duplicate_rate,
                "frequency": frequency,
                "ctr_drop_percent": ctr_drop_percent,
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37Y",
        "status": "saturation_monitor_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "campaign_mutation_used": False,
        "saturation": {
            "score": saturation_score,
            "risk_level": risk_level,
            "duplicate_rate": duplicate_rate,
            "duplicate_count": moat["duplicate_count"],
            "frequency": frequency,
            "ctr_drop_percent": ctr_drop_percent,
        },
        "recommendations": recommendations,
        "source_modules": {
            "data_moat": moat["mission"],
            "opportunity_alerts": alerts["mission"],
        },
        "blocked_reasons": sorted(set(blocked)),
        "human_review_required": risk_level != "low" or bool(blocked),
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
