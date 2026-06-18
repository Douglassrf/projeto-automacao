from __future__ import annotations

from typing import Any

from app.core.country_intelligence import country_intelligence_profile
from app.core.creative_intelligence import creative_intelligence_analysis
from app.core.landing_intelligence import landing_intelligence_analysis
from app.core.market_radar import market_radar_local_report
from app.core.offer_intelligence import offer_intelligence_analysis
from app.core.winning_ad_score import winning_ad_score
from app.services.campaign_brain import CampaignBrainAgent


def global_opportunity_brief(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    creative = creative_intelligence_analysis(payload)
    landing = landing_intelligence_analysis(payload)
    offer = offer_intelligence_analysis(payload)
    country = country_intelligence_profile(payload)
    score = winning_ad_score(payload)
    radar = market_radar_local_report({"signals": payload.get("signals") or [payload]})

    blockers = []
    for section in (creative, landing, offer, country, score):
        blockers.extend(section.get("blocked_reasons") or [])

    risk_flags = []
    if creative.get("analysis"):
        risk_flags.extend(creative["analysis"].get("risk_flags") or [])
    if landing.get("analysis"):
        risk_flags.extend(landing["analysis"].get("risk_flags") or [])
    if offer.get("analysis"):
        risk_flags.extend(offer["analysis"].get("risk_flags") or [])

    global_score = score.get("score", {}).get("global_score") if score.get("score") else 0
    ready_sections = sum(
        1
        for section in (creative, landing, offer, country)
        if section["status"] in {"creative_ready", "landing_ready", "offer_ready", "country_ready"}
    )
    decision = "sandbox_review_ready" if not blockers and not risk_flags and ready_sections >= 4 and global_score >= 70 else "needs_revision"

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Global Opportunity Brief",
            "niche": offer.get("analysis", {}).get("niche", "unknown") if offer.get("analysis") else "unknown",
            "campaign_stage": "37H",
            "outcome": decision,
            "lesson": "Global Opportunity Brief deve consolidar criativo, landing, oferta, pais, score e radar antes de qualquer execucao.",
            "metrics": {
                "global_score": global_score,
                "ready_sections": ready_sections,
                "risk_flags": risk_flags,
                "blockers": blockers,
            },
        }
    )

    return {
        "mission": "37H",
        "status": decision,
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "ready_for_operator": False,
        "summary": {
            "country": country["country"],
            "niche": offer.get("analysis", {}).get("niche") if offer.get("analysis") else "unknown",
            "global_score": global_score,
            "winning_verdict": score.get("score", {}).get("verdict") if score.get("score") else "blocked",
            "top_opportunity": radar["opportunities"][0] if radar["opportunities"] else None,
            "ready_sections": ready_sections,
        },
        "sections": {
            "creative": creative,
            "landing": landing,
            "offer": offer,
            "country": country,
            "winning_score": score,
            "market_radar": radar,
        },
        "blockers": sorted(set(blockers)),
        "risk_flags": sorted(set(risk_flags)),
        "recommended_next_step": (
            "revisar com humano e preparar sandbox pausado"
            if decision == "sandbox_review_ready"
            else "corrigir secoes com risco antes de qualquer sandbox"
        ),
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
