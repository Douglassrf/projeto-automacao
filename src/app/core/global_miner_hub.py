from __future__ import annotations

from collections import Counter
from typing import Any

from app.core.global_intelligence_contract import normalize_global_ad_signal
from app.core.market_radar import market_radar_local_report
from app.services.campaign_brain import CampaignBrainAgent


def global_miner_hub_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    raw_signals = payload.get("signals") or []
    if not isinstance(raw_signals, list):
        raw_signals = []

    normalized = [normalize_global_ad_signal(signal) for signal in raw_signals]
    accepted = [item for item in normalized if item["status"] == "normalized"]
    blocked = [item for item in normalized if item["status"] != "normalized"]
    accepted_signals = [item["normalized_signal"] for item in accepted]
    platform_counts = Counter(signal["platform"] for signal in accepted_signals)
    country_counts = Counter(signal["country"] for signal in accepted_signals)
    blocked_reasons = Counter(reason for item in blocked for reason in item["blocked_reasons"])
    radar_input = [
        {
            "platform": signal["platform"],
            "country": signal["country"],
            "language": signal["language"],
            "currency": signal["currency"],
            "headline": signal["creative"]["headline"],
            "body": signal["creative"]["body"],
            "cta": signal["creative"]["cta"],
            "format": signal["creative"]["format"],
            "landing_url": signal["landing"]["url"],
            "domain": signal["landing"]["domain"],
            "niche": signal["offer"]["niche"],
            "ticket": signal["offer"]["ticket"],
            "impressions": signal["metrics"]["impressions"],
            "clicks": signal["metrics"]["clicks"],
            "spend": signal["metrics"]["spend"],
            "conversions": signal["metrics"]["conversions"],
        }
        for signal in accepted_signals
    ]
    radar = market_radar_local_report({"signals": radar_input})

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Global Miner Hub Local",
            "niche": radar["opportunities"][0]["niche"] if radar["opportunities"] else "sem sinal",
            "campaign_stage": "37K",
            "outcome": "miner_batch_ready" if accepted else "insufficient_data",
            "lesson": "Global Miner Hub deve agregar sinais locais de multiplas plataformas antes de qualquer coleta externa.",
            "metrics": {
                "signals_received": len(raw_signals),
                "signals_accepted": len(accepted),
                "signals_blocked": len(blocked),
                "platform_counts": dict(platform_counts),
            },
        }
    )

    return {
        "mission": "37K",
        "status": "miner_batch_ready" if accepted else "insufficient_data",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "browser_used": False,
        "signals_received": len(raw_signals),
        "signals_accepted": len(accepted),
        "signals_blocked": len(blocked),
        "platform_counts": dict(platform_counts),
        "country_counts": dict(country_counts),
        "blocked_reasons": dict(blocked_reasons),
        "radar": {
            "status": radar["status"],
            "opportunities": radar["opportunities"],
        },
        "normalized_preview": accepted_signals[:5],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
