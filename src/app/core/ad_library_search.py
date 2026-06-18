from __future__ import annotations

from typing import Any

from app.core.ad_library_model import ad_library_data_model
from app.core.global_miner_hub import global_miner_hub_local
from app.services.campaign_brain import CampaignBrainAgent


def _matches_query(signal: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    searchable = " ".join(
        [
            str(signal.get("platform", "")),
            str(signal.get("country", "")),
            str(signal.get("language", "")),
            str(signal.get("creative", {}).get("headline", "")),
            str(signal.get("creative", {}).get("body", "")),
            str(signal.get("creative", {}).get("cta", "")),
            str(signal.get("offer", {}).get("niche", "")),
            str(signal.get("offer", {}).get("type", "")),
        ]
    ).lower()
    return query.lower() in searchable


def ad_library_search_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    blocked: list[str] = []
    if bool(payload.get("external_search")):
        blocked.append("external_search_forbidden_in_local_readiness")
    if bool(payload.get("database_search")):
        blocked.append("database_search_forbidden_in_local_readiness")

    model = ad_library_data_model(payload)
    miner = global_miner_hub_local(payload)
    blocked.extend(model["blocked_reasons"])
    query = str(payload.get("query") or payload.get("q") or "").strip()
    platform_filter = str(payload.get("platform_filter") or "").lower().strip()
    country_filter = str(payload.get("country_filter") or "").upper().strip()
    niche_filter = str(payload.get("niche_filter") or "").lower().strip()

    filtered = []
    for idx, signal in enumerate(miner["normalized_preview"][:20]):
        if platform_filter and signal["platform"] != platform_filter:
            continue
        if country_filter and signal["country"] != country_filter:
            continue
        if niche_filter and signal["offer"]["niche"].lower() != niche_filter:
            continue
        if not _matches_query(signal, query):
            continue
        fingerprint = model["records_preview"][idx]["fingerprint"] if idx < len(model["records_preview"]) else f"preview_{idx}"
        filtered.append(
            {
                "ad_id": f"ad_{fingerprint}",
                "fingerprint": fingerprint,
                "platform": signal["platform"],
                "country": signal["country"],
                "language": signal["language"],
                "niche": signal["offer"]["niche"],
                "headline": signal["creative"]["headline"],
                "cta": signal["creative"]["cta"],
                "score_hint": min(100, 50 + int(signal["metrics"].get("ctr_percent", 0))),
            }
        )

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Ad Library Search Local",
            "niche": niche_filter or (filtered[0]["niche"] if filtered else "sem resultado"),
            "campaign_stage": "37U",
            "outcome": "ad_library_search_ready" if not blocked else "blocked",
            "lesson": "Busca da biblioteca deve funcionar primeiro em memoria local de preview, sem scraping, banco real ou consulta externa.",
            "metrics": {
                "results": len(filtered),
                "query": query,
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37U",
        "status": "ad_library_search_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "database_read_used": False,
        "large_local_storage_used": False,
        "search_index_built_in_memory": True,
        "query": query,
        "filters": {
            "platform": platform_filter or None,
            "country": country_filter or None,
            "niche": niche_filter or None,
        },
        "results_count": len(filtered),
        "results_preview": filtered[:10],
        "blocked_reasons": sorted(set(blocked)),
        "next_steps": [
            "conectar ao schema Ad Library somente em ambiente servidor",
            "adicionar busca vetorial por tenant quando pgvector estiver ativo",
            "manter scraping externo e API real atras de approval/compliance",
        ],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
