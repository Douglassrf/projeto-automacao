from __future__ import annotations

from typing import Any

from app.services.campaign_brain import CampaignBrainAgent


COUNTRY_PROFILES: dict[str, dict[str, Any]] = {
    "US": {"name": "United States", "languages": ["en-US"], "currency": "USD", "market_tier": "tier_1", "priority_score": 95},
    "CA": {"name": "Canada", "languages": ["en-CA", "fr-CA"], "currency": "CAD", "market_tier": "tier_1", "priority_score": 88},
    "GB": {"name": "United Kingdom", "languages": ["en-GB"], "currency": "GBP", "market_tier": "tier_1", "priority_score": 86},
    "AU": {"name": "Australia", "languages": ["en-AU"], "currency": "AUD", "market_tier": "tier_1", "priority_score": 82},
    "DE": {"name": "Germany", "languages": ["de-DE"], "currency": "EUR", "market_tier": "tier_1_eu", "priority_score": 78},
    "FR": {"name": "France", "languages": ["fr-FR"], "currency": "EUR", "market_tier": "tier_1_eu", "priority_score": 76},
    "ES": {"name": "Spain", "languages": ["es-ES"], "currency": "EUR", "market_tier": "tier_2_eu", "priority_score": 70},
    "PT": {"name": "Portugal", "languages": ["pt-PT"], "currency": "EUR", "market_tier": "tier_2_eu", "priority_score": 66},
    "BR": {"name": "Brazil", "languages": ["pt-BR"], "currency": "BRL", "market_tier": "latam", "priority_score": 64},
}


def country_intelligence_profile(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    country = str(payload.get("country") or payload.get("geo") or "BR").upper()
    niche = str(payload.get("niche") or "unknown")
    profile = COUNTRY_PROFILES.get(country)
    blocked: list[str] = []
    if profile is None:
        blocked.append("unsupported_country")
        profile = {"name": country, "languages": [], "currency": "", "market_tier": "unknown", "priority_score": 0}

    recommended_language = str(payload.get("language") or (profile["languages"][0] if profile["languages"] else ""))
    recommended_currency = str(payload.get("currency") or profile["currency"])
    budget_hint = "high_ticket_saas" if country in {"US", "CA", "GB", "AU"} and niche in {"saas", "b2b"} else "controlled_test"

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Country Intelligence {country}",
            "niche": niche,
            "campaign_stage": "37E",
            "outcome": "country_ready" if not blocked else "blocked",
            "lesson": "Country Intelligence deve orientar idioma, moeda e prioridade antes de expandir campanha global.",
            "metrics": {
                "country": country,
                "priority_score": profile["priority_score"],
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37E",
        "status": "country_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "country": country,
        "profile": profile,
        "recommended_language": recommended_language,
        "recommended_currency": recommended_currency,
        "budget_hint": budget_hint,
        "blocked_reasons": blocked,
        "market_entry_notes": [
            "validar criativo e oferta no idioma local",
            "usar pagina/checkout compativel com moeda local",
            "comecar por sandbox ou campanha pausada antes de qualquer gasto",
        ],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
