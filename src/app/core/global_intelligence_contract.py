from __future__ import annotations

from typing import Any

from app.services.campaign_brain import CampaignBrainAgent


SUPPORTED_PLATFORMS = {"meta", "google", "tiktok", "linkedin", "pinterest"}


def _text(payload: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _number(payload: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = payload.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def normalize_global_ad_signal(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    platform = _text(payload, "platform", "source", default="meta").lower()
    country = _text(payload, "country", "geo", default="BR").upper()
    language = _text(payload, "language", "lang", default="pt-BR")
    currency = _text(payload, "currency", "currency_code", default="BRL").upper()
    headline = _text(payload, "headline", "title", "ad_title")
    body = _text(payload, "body", "text", "description", "primary_text")
    cta = _text(payload, "cta", "call_to_action", default="LEARN_MORE")
    landing_url = _text(payload, "landing_url", "url", "destination_url")
    impressions = _number(payload, "impressions", "views")
    clicks = _number(payload, "clicks", "link_clicks")
    spend = _number(payload, "spend", "cost")
    conversions = _number(payload, "conversions", "leads", "purchases")

    blocked: list[str] = []
    if platform not in SUPPORTED_PLATFORMS:
        blocked.append("unsupported_platform")
    if not headline:
        blocked.append("headline_required")
    if not body:
        blocked.append("body_required")
    if impressions < 0 or clicks < 0 or spend < 0 or conversions < 0:
        blocked.append("negative_metric_forbidden")

    ctr = round((clicks / impressions) * 100, 4) if impressions else 0.0
    cpa = round(spend / conversions, 4) if conversions else 0.0
    signal_quality = 100
    signal_quality -= 25 if not headline else 0
    signal_quality -= 25 if not body else 0
    signal_quality -= 15 if not landing_url else 0
    signal_quality -= 15 if not impressions else 0
    signal_quality -= 20 if blocked else 0
    signal_quality = max(signal_quality, 0)

    normalized = {
        "platform": platform,
        "country": country,
        "language": language,
        "currency": currency,
        "creative": {
            "headline": headline,
            "body": body,
            "cta": cta,
            "format": _text(payload, "format", "creative_format", default="unknown"),
        },
        "landing": {
            "url": landing_url,
            "domain": _text(payload, "domain", "landing_domain"),
        },
        "offer": {
            "niche": _text(payload, "niche", "vertical", default="unknown"),
            "ticket": _number(payload, "ticket", "price"),
        },
        "metrics": {
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
            "conversions": conversions,
            "ctr_percent": ctr,
            "cpa": cpa,
        },
    }

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Global Signal {platform}",
            "niche": normalized["offer"]["niche"],
            "campaign_stage": "37A",
            "outcome": "normalized" if not blocked else "blocked",
            "lesson": "Global Intelligence deve normalizar dados por plataforma antes de enviar ao Brain.",
            "metrics": {
                "signal_quality": signal_quality,
                "blocked_reasons": blocked,
                "platform": platform,
            },
        }
    )

    return {
        "mission": "37A",
        "status": "normalized" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "normalized_signal": normalized,
        "blocked_reasons": blocked,
        "signal_quality": signal_quality,
        "universal_contract": {
            "required_blocks": ["platform", "country", "creative", "landing", "offer", "metrics"],
            "supported_platforms": sorted(SUPPORTED_PLATFORMS),
            "brain_safe": True,
            "operator_safe": False,
        },
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
