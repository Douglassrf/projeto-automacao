from __future__ import annotations

from typing import Any

from app.core.global_intelligence_contract import normalize_global_ad_signal
from app.services.campaign_brain import CampaignBrainAgent


def _score_creative(signal: dict[str, Any]) -> int:
    creative = signal["creative"]
    score = 0
    headline = creative["headline"]
    body = creative["body"]
    cta = creative["cta"]
    score += 30 if len(headline) >= 8 else 10 if headline else 0
    score += 35 if len(body) >= 20 else 15 if body else 0
    score += 20 if cta and cta != "LEARN_MORE" else 10 if cta else 0
    score += 15 if creative["format"] in {"video", "video_ugc_15s", "short_video"} else 8
    return min(score, 100)


def _score_landing(signal: dict[str, Any]) -> int:
    landing = signal["landing"]
    if not landing["url"]:
        return 25
    score = 70
    score += 15 if landing["url"].startswith("https://") else 0
    score += 15 if landing["domain"] or "." in landing["url"] else 0
    return min(score, 100)


def _score_offer(signal: dict[str, Any]) -> int:
    offer = signal["offer"]
    score = 45 if offer["niche"] == "unknown" else 70
    ticket = float(offer["ticket"] or 0)
    if ticket > 0:
        score += 15
    if 10 <= ticket <= 500 or ticket == 0:
        score += 15
    return min(score, 100)


def _score_performance(signal: dict[str, Any]) -> int:
    metrics = signal["metrics"]
    ctr = metrics["ctr_percent"]
    conversions = metrics["conversions"]
    cpa = metrics["cpa"]
    score = 35
    score += min(30, ctr * 6)
    score += min(20, conversions * 4)
    if cpa and cpa <= 10:
        score += 15
    elif cpa:
        score += max(0, 15 - cpa * 0.5)
    return min(round(score), 100)


def winning_ad_score(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    normalized = normalize_global_ad_signal(payload)
    if normalized["status"] != "normalized":
        return {
            "mission": "37C",
            "status": "blocked",
            "will_execute_real_action": False,
            "will_activate_spend": False,
            "blocked_reasons": normalized["blocked_reasons"],
            "score": None,
            "normalized_signal": normalized["normalized_signal"],
        }

    signal = normalized["normalized_signal"]
    creative_score = _score_creative(signal)
    landing_score = _score_landing(signal)
    offer_score = _score_offer(signal)
    performance_score = _score_performance(signal)
    trend_score = int(max(0, min(100, float(payload.get("trend_score") or payload.get("heat_score") or 50))))
    global_score = round(
        creative_score * 0.28
        + landing_score * 0.18
        + offer_score * 0.18
        + performance_score * 0.24
        + trend_score * 0.12
    )
    verdict = "likely_winner" if global_score >= 80 else "needs_iteration" if global_score >= 60 else "high_risk"

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Winning Score {signal['platform']}",
            "niche": signal["offer"]["niche"],
            "campaign_stage": "37C",
            "outcome": verdict,
            "lesson": "Winning Ad Score deve classificar criativo, landing, oferta, performance e tendencia antes de execucao.",
            "metrics": {
                "global_score": global_score,
                "creative_score": creative_score,
                "landing_score": landing_score,
                "offer_score": offer_score,
                "performance_score": performance_score,
                "trend_score": trend_score,
            },
        }
    )

    return {
        "mission": "37C",
        "status": "scored",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "score": {
            "creative_score": creative_score,
            "landing_score": landing_score,
            "offer_score": offer_score,
            "performance_score": performance_score,
            "trend_score": trend_score,
            "global_score": global_score,
            "verdict": verdict,
        },
        "normalized_signal": signal,
        "recommended_next_step": "analisar angulo criativo antes de qualquer execucao" if verdict != "likely_winner" else "validar em sandbox pausado antes de escalar",
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
