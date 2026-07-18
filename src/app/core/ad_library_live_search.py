"""Missão 37V — Garimpo real de anúncio (Meta Ad Library API).

Contexto: `ad_library_search_local` (Missão 37U) e `global_miner_hub_local`
(Missão 37K) processam apenas sinais que o próprio chamador envia no
payload — nunca saem buscando anúncio nenhum na internet sozinhas (isso é
documentado explicitamente nos dois módulos: `network_access_used: False`).
Esta missão adiciona a peça que faltava: uma busca real na Meta Ad Library
API (oficial, gratuita, somente leitura) e conecta o resultado direto no
motor de normalização/score já existente (`normalize_global_ad_signal`,
`winning_ad_score`), sem duplicar lógica de pontuação.

Guardrails:
- Somente leitura: nunca cria, publica ou paga nada.
- Respeita o dry-run global do Meta client (`META_DRY_RUN` /
  `META_ACCESS_TOKEN`) — sem credencial real configurada, devolve amostra
  simulada e claramente marcada, nunca falha silenciosamente nem finge um
  resultado real.
- Ad Library API real não devolve métricas de performance (impressões,
  cliques, gasto, conversões) para anúncios comerciais comuns — isso é
  reportado de forma explícita em `notes`, para não sugerir um dado que a
  fonte real não fornece.
"""

from __future__ import annotations

from typing import Any

from app.core.global_intelligence_contract import normalize_global_ad_signal
from app.integrations.meta_marketing import MetaMarketingClient, MetaMarketingError
from app.services.campaign_brain import CampaignBrainAgent


def _map_meta_ad_library_result(raw: dict[str, Any], niche_hint: str, country_hint: str) -> dict[str, Any]:
    bodies = raw.get("ad_creative_bodies") or []
    titles = raw.get("ad_creative_link_titles") or []
    languages = raw.get("languages") or []
    return {
        "platform": "meta",
        "source": "meta_ad_library_live",
        "country": country_hint,
        "language": languages[0] if languages else "pt-BR",
        "headline": titles[0] if titles else str(raw.get("page_name") or ""),
        "body": bodies[0] if bodies else "",
        "cta": "LEARN_MORE",
        "landing_url": raw.get("ad_snapshot_url") or "",
        "niche": niche_hint,
        "format": "unknown",
    }


def ad_library_search_live(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    query = str(payload.get("query") or payload.get("q") or payload.get("search_terms") or "").strip()
    countries = payload.get("countries") or [str(payload.get("country_filter") or "BR").upper()]
    if not isinstance(countries, list) or not countries:
        countries = ["BR"]
    niche_hint = str(payload.get("niche_filter") or payload.get("niche") or "unknown")
    limit = max(1, min(int(payload.get("limit") or 10), 25))

    blocked: list[str] = []
    if not query:
        blocked.append("query_required")

    client = MetaMarketingClient()

    if blocked:
        return {
            "mission": "37V",
            "status": "blocked",
            "will_execute_real_action": False,
            "will_activate_spend": False,
            "network_access_used": False,
            "dry_run": client.dry_run,
            "query": query,
            "blocked_reasons": blocked,
            "results_count": 0,
            "results_preview": [],
        }

    try:
        raw = client.search_ad_library(search_terms=query, countries=countries, limit=limit)
    except MetaMarketingError as exc:
        return {
            "mission": "37V",
            "status": "error",
            "will_execute_real_action": False,
            "will_activate_spend": False,
            "network_access_used": not client.dry_run,
            "dry_run": client.dry_run,
            "query": query,
            "blocked_reasons": [f"meta_ad_library_error: {exc}"],
            "results_count": 0,
            "results_preview": [],
        }

    normalized_results: list[dict[str, Any]] = []
    for item in (raw.get("data") or [])[:limit]:
        mapped = _map_meta_ad_library_result(item, niche_hint, countries[0])
        norm = normalize_global_ad_signal(mapped)
        if norm["status"] == "normalized":
            normalized_results.append(
                {
                    "meta_ad_archive_id": item.get("id"),
                    "page_name": item.get("page_name"),
                    "ad_snapshot_url": item.get("ad_snapshot_url"),
                    "normalized_signal": norm["normalized_signal"],
                }
            )

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Ad Library Live Search: {query}",
            "niche": niche_hint,
            "campaign_stage": "37V",
            "outcome": "ad_library_live_search_ready" if normalized_results else "no_results",
            "lesson": "Garimpo real deve normalizar cada anúncio encontrado pelo mesmo contrato usado no Winning Ad Score, sem duplicar lógica de pontuação.",
            "metrics": {
                "results": len(normalized_results),
                "query": query,
                "dry_run": raw.get("dry_run", client.dry_run),
            },
        }
    )

    return {
        "mission": "37V",
        "status": "ad_library_live_search_ready" if normalized_results else "no_results",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": not raw.get("dry_run", client.dry_run),
        "dry_run": raw.get("dry_run", client.dry_run),
        "query": query,
        "countries": countries,
        "results_count": len(normalized_results),
        "results_preview": normalized_results,
        "source": "meta_ad_library_api" if not raw.get("dry_run", client.dry_run) else "meta_ad_library_api_dry_run_simulated",
        "notes": [
            "Meta Ad Library API não expõe métricas de performance (impressões/cliques/gasto/conversões) "
            "para anúncios comerciais comuns — apenas metadados de criativo. Use winning-ad-score com "
            "métricas reais suas (ou de outra fonte) para pontuar performance.",
            "Somente leitura: nenhuma campanha, gasto ou publicação é executada por esta rota.",
        ],
        "recommended_next_step": "enviar normalized_signal de cada resultado para /global-intelligence/winning-ad-score",
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
