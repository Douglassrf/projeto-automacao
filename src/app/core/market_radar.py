from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.core.global_intelligence_contract import normalize_global_ad_signal
from app.services.campaign_brain import CampaignBrainAgent


def market_radar_local_report(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    raw_signals = payload.get("signals") or []
    if not isinstance(raw_signals, list):
        raw_signals = []

    normalized = [normalize_global_ad_signal(signal) for signal in raw_signals]
    accepted = [item for item in normalized if item["status"] == "normalized"]
    blocked = [item for item in normalized if item["status"] != "normalized"]
    groups: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "signals": 0,
            "impressions": 0.0,
            "clicks": 0.0,
            "spend": 0.0,
            "conversions": 0.0,
            "quality_total": 0.0,
        }
    )

    for item in accepted:
        signal = item["normalized_signal"]
        key = (signal["platform"], signal["country"], signal["offer"]["niche"])
        group = groups[key]
        group["signals"] += 1
        group["quality_total"] += item["signal_quality"]
        for metric in ("impressions", "clicks", "spend", "conversions"):
            group[metric] += signal["metrics"][metric]

    opportunities = []
    for (platform, country, niche), group in groups.items():
        ctr = round((group["clicks"] / group["impressions"]) * 100, 4) if group["impressions"] else 0.0
        cpa = round(group["spend"] / group["conversions"], 4) if group["conversions"] else 0.0
        avg_quality = round(group["quality_total"] / group["signals"], 2) if group["signals"] else 0.0
        heat_score = min(100, round(avg_quality * 0.45 + ctr * 7 + group["conversions"] * 3 - cpa * 0.4, 2))
        opportunities.append(
            {
                "platform": platform,
                "country": country,
                "niche": niche,
                "signals": group["signals"],
                "ctr_percent": ctr,
                "cpa": cpa,
                "conversions": group["conversions"],
                "heat_score": max(0, heat_score),
            }
        )

    opportunities.sort(key=lambda item: item["heat_score"], reverse=True)
    top = opportunities[:5]
    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Market Radar Local",
            "niche": top[0]["niche"] if top else "sem sinal",
            "campaign_stage": "37B",
            "outcome": "radar_ready" if top else "insufficient_data",
            "lesson": "Market Radar deve ranquear oportunidades por sinais normalizados antes de sugerir execucao.",
            "metrics": {
                "signals": len(raw_signals),
                "accepted": len(accepted),
                "blocked": len(blocked),
                "top_heat_score": top[0]["heat_score"] if top else 0,
            },
        }
    )

    return {
        "mission": "37B",
        "status": "radar_ready" if top else "insufficient_data",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "signals_received": len(raw_signals),
        "signals_accepted": len(accepted),
        "signals_blocked": len(blocked),
        "opportunities": top,
        "blocked_summary": [item["blocked_reasons"] for item in blocked],
        "recommendation": (
            "Priorizar estudo criativo/oferta do primeiro nicho ranqueado; nao executar campanha ainda."
            if top
            else "Coletar mais sinais normalizados antes de decidir."
        ),
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
