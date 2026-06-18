from __future__ import annotations

from typing import Any

from app.core.global_intelligence_contract import normalize_global_ad_signal
from app.services.campaign_brain import CampaignBrainAgent


URGENCY_TERMS = {"agora", "hoje", "ultimas vagas", "last chance", "limited time", "only today"}
PROOF_TERMS = {"case", "prova", "resultado", "dados", "teste", "before", "after", "metric"}
RISK_TERMS = {"garantido", "100%", "sem risco", "resultado garantido", "dinheiro facil", "get rich"}
EMOTION_TERMS = {
    "fear": {"perder", "risco", "erro", "wasting", "fail", "stop"},
    "gain": {"lucro", "crescer", "profit", "scale", "winner", "winning"},
    "curiosity": {"descubra", "segredo", "find", "why", "como", "testei"},
    "relief": {"simples", "facil", "sem complicacao", "easy", "faster"},
}


def _contains_any(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _dominant_emotion(text: str) -> str:
    lowered = text.lower()
    scores = {
        emotion: sum(1 for term in terms if term in lowered)
        for emotion, terms in EMOTION_TERMS.items()
    }
    emotion, score = max(scores.items(), key=lambda item: item[1])
    return emotion if score else "neutral"


def creative_intelligence_analysis(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    normalized = normalize_global_ad_signal(payload)
    signal = normalized["normalized_signal"]
    creative = signal["creative"]
    headline = creative["headline"]
    body = creative["body"]
    text = f"{headline} {body} {creative['cta']}"

    if normalized["status"] != "normalized":
        return {
            "mission": "37D",
            "status": "blocked",
            "will_execute_real_action": False,
            "will_activate_spend": False,
            "blocked_reasons": normalized["blocked_reasons"],
            "analysis": None,
        }

    hook_strength = 30
    hook_strength += 25 if len(headline) >= 12 else 5
    hook_strength += 20 if _contains_any(text, PROOF_TERMS) else 0
    hook_strength += 15 if _contains_any(text, URGENCY_TERMS) else 0
    hook_strength += 10 if creative["cta"] and creative["cta"] != "LEARN_MORE" else 0
    hook_strength = min(hook_strength, 100)
    risk_flags = []
    if _contains_any(text, RISK_TERMS):
        risk_flags.append("risky_absolute_or_income_claim")
    if len(body) < 20:
        risk_flags.append("body_too_short")

    angle = "proof_driven" if _contains_any(text, PROOF_TERMS) else "urgency_driven" if _contains_any(text, URGENCY_TERMS) else "problem_solution"
    clarity_score = min(100, 40 + (25 if headline else 0) + (25 if len(body) >= 20 else 5) + (10 if creative["cta"] else 0))
    creative_score = max(0, round((hook_strength * 0.45 + clarity_score * 0.45) - len(risk_flags) * 12))

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Creative Intelligence {signal['platform']}",
            "niche": signal["offer"]["niche"],
            "campaign_stage": "37D",
            "outcome": "creative_ready" if creative_score >= 70 and not risk_flags else "needs_revision",
            "lesson": "Creative Intelligence deve explicar angulo, emocao, clareza e riscos antes do score final.",
            "metrics": {
                "creative_score": creative_score,
                "hook_strength": hook_strength,
                "clarity_score": clarity_score,
                "risk_flags": risk_flags,
            },
        }
    )

    return {
        "mission": "37D",
        "status": "creative_ready" if creative_score >= 70 and not risk_flags else "needs_revision",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "analysis": {
            "angle": angle,
            "dominant_emotion": _dominant_emotion(text),
            "hook_strength": hook_strength,
            "clarity_score": clarity_score,
            "creative_score": creative_score,
            "risk_flags": risk_flags,
            "cta": creative["cta"],
            "format": creative["format"],
        },
        "recommended_next_step": "usar no Winning Ad Score" if creative_score >= 70 and not risk_flags else "revisar promessa, corpo do texto ou CTA antes de testar",
        "normalized_signal": signal,
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
