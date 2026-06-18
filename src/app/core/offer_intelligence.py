from __future__ import annotations

from typing import Any

from app.core.global_intelligence_contract import normalize_global_ad_signal
from app.services.campaign_brain import CampaignBrainAgent


HIGH_VALUE_NICHES = {"saas", "b2b", "finance", "education", "health", "ecommerce"}
RISKY_OFFER_TERMS = {"garantido", "100%", "dinheiro facil", "sem esforco", "cura", "milionario"}


def offer_intelligence_analysis(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    normalized = normalize_global_ad_signal(payload)
    signal = normalized["normalized_signal"]
    offer = signal["offer"]
    text = f"{signal['creative']['headline']} {signal['creative']['body']} {payload.get('offer_description', '')}".lower()
    ticket = float(offer["ticket"] or payload.get("ticket") or 0)
    recurrence = str(payload.get("recurrence") or payload.get("billing") or "none").lower()
    niche = str(offer["niche"] or "unknown").lower()
    blocked = list(normalized["blocked_reasons"])

    risk_flags = []
    if any(term in text for term in RISKY_OFFER_TERMS):
        risk_flags.append("risky_offer_claim")
    if ticket < 0:
        blocked.append("negative_ticket_forbidden")
    if niche == "unknown":
        risk_flags.append("niche_unknown")

    value_score = 30
    value_score += 20 if niche in HIGH_VALUE_NICHES else 5
    value_score += 20 if ticket >= 50 else 12 if ticket > 0 else 5
    value_score += 20 if recurrence in {"monthly", "annual", "subscription", "recurring"} else 8
    value_score += 10 if payload.get("proof") or payload.get("social_proof") else 0
    value_score = min(value_score, 100)
    offer_score = max(0, value_score - len(risk_flags) * 15 - len(blocked) * 20)
    market_fit = "premium_recurring" if ticket >= 50 and recurrence in {"monthly", "annual", "subscription", "recurring"} else "low_ticket_test" if ticket < 50 else "one_time_offer"

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Offer Intelligence {signal['platform']}",
            "niche": niche,
            "campaign_stage": "37G",
            "outcome": "offer_ready" if not blocked and offer_score >= 70 and not risk_flags else "needs_revision",
            "lesson": "Offer Intelligence deve avaliar ticket, recorrencia, nicho e risco antes de campanha.",
            "metrics": {
                "offer_score": offer_score,
                "ticket": ticket,
                "recurrence": recurrence,
                "risk_flags": risk_flags,
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37G",
        "status": "blocked" if blocked else "offer_ready" if offer_score >= 70 and not risk_flags else "needs_revision",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "blocked_reasons": blocked,
        "analysis": {
            "offer_score": offer_score,
            "value_score": value_score,
            "niche": niche,
            "ticket": ticket,
            "recurrence": recurrence,
            "market_fit": market_fit,
            "risk_flags": risk_flags,
        },
        "recommended_next_step": "combinar com score criativo/landing antes de sandbox" if offer_score >= 70 and not risk_flags else "ajustar promessa, nicho, prova ou ticket antes de testar",
        "normalized_signal": signal,
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
