from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.core.global_intelligence_contract import normalize_global_ad_signal
from app.services.campaign_brain import CampaignBrainAgent


def landing_intelligence_analysis(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    normalized = normalize_global_ad_signal(payload)
    signal = normalized["normalized_signal"]
    url = signal["landing"]["url"]
    parsed = urlparse(url) if url else None
    blocked = list(normalized["blocked_reasons"])
    if not url:
        blocked.append("landing_url_required")

    is_https = bool(parsed and parsed.scheme == "https")
    has_domain = bool(parsed and parsed.netloc and "." in parsed.netloc)
    path_depth = len([part for part in (parsed.path.split("/") if parsed else []) if part])
    cta_match = signal["creative"]["cta"] != "LEARN_MORE"
    funnel_type = str(payload.get("funnel_type") or payload.get("destination") or signal["creative"]["cta"]).lower()
    lead_ready = funnel_type in {"lead", "whatsapp", "signup", "sign_up", "form", "demo"}

    score = 0
    score += 35 if is_https else 10 if url else 0
    score += 25 if has_domain else 0
    score += 15 if path_depth <= 2 else 8
    score += 15 if lead_ready else 5
    score += 10 if cta_match else 0
    score = min(score, 100)

    risk_flags = []
    if not is_https:
        risk_flags.append("landing_not_https")
    if not has_domain:
        risk_flags.append("landing_domain_invalid")
    if not lead_ready:
        risk_flags.append("funnel_goal_unclear")

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Landing Intelligence {signal['platform']}",
            "niche": signal["offer"]["niche"],
            "campaign_stage": "37F",
            "outcome": "landing_ready" if score >= 75 and not risk_flags else "needs_revision",
            "lesson": "Landing Intelligence deve avaliar seguranca, dominio, CTA e funil antes de campanha.",
            "metrics": {
                "landing_score": score,
                "risk_flags": risk_flags,
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37F",
        "status": "blocked" if blocked else "landing_ready" if score >= 75 and not risk_flags else "needs_revision",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "blocked_reasons": blocked,
        "analysis": {
            "landing_score": score,
            "is_https": is_https,
            "has_domain": has_domain,
            "path_depth": path_depth,
            "funnel_type": funnel_type,
            "lead_ready": lead_ready,
            "cta_match": cta_match,
            "risk_flags": risk_flags,
        },
        "recommended_next_step": "usar no Winning Ad Score" if score >= 75 and not risk_flags else "corrigir URL, funil ou CTA antes de testar",
        "normalized_signal": signal,
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
