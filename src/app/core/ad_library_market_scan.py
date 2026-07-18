"""Missão 37W — Termômetro de recorrência (garimpo de produto campeão).

Regra de negócio definida pelo Douglas (dono do produto, 18/07/2026): o
sinal usado para decidir se um produto/oferta é "campeão" não é uma nota
qualquer — é contar quantas variações de anúncio da MESMA página estão
ativas ao mesmo tempo nos mercados de Euro, Dólar e Real. Um anunciante
mantendo 15-20+ variações rodando ao mesmo tempo, por tempo prolongado, é
o termômetro de que aquele produto vende e vale remodelar/copiar o
ângulo. Poucos anúncios isolados = sinal fraco, não é pra copiar.

Isto é uma HEURÍSTICA DE NEGÓCIO, não um fato calculado pela Meta — a Ad
Library API não informa vendas, receita ou lucro de ninguém. O que ela
informa é volume de anúncio ativo por página, e este módulo conta esse
volume e aplica o limiar que o Douglas definiu. Isso precisa ficar
explícito em toda resposta (`heuristic_disclaimer`), conforme a regra 7 do
CLAUDE.md do projeto: julgamento qualitativo tem que ser documentado como
heurística, nunca apresentado como fato calculado.

Reaproveita o mesmo client (`MetaMarketingClient.search_ad_library`) e o
mesmo guardrail de dry-run já usados pela Missão 37V — nenhuma chamada real
sai sem META_DRY_RUN=false + credenciais Meta configuradas.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.integrations.meta_marketing import MetaMarketingClient, MetaMarketingError
from app.services.campaign_brain import CampaignBrainAgent
from app.services.meta_campaign_operator import GEO_PRESETS

DEFAULT_STRONG_MARKETS = ("EURO_TIER", "USD_TIER1", "BRASIL")


def ad_library_market_scan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    query = str(payload.get("query") or payload.get("q") or payload.get("search_terms") or "").strip()
    geo_presets = payload.get("geo_presets") or list(DEFAULT_STRONG_MARKETS)
    if not isinstance(geo_presets, list) or not geo_presets:
        geo_presets = list(DEFAULT_STRONG_MARKETS)
    min_recurring_ads = int(payload.get("min_recurring_ads") or 15)
    limit_per_market = max(1, min(int(payload.get("limit_per_market") or 100), 100))

    blocked: list[str] = []
    if not query:
        blocked.append("query_required")
    unknown_presets = [preset for preset in geo_presets if preset not in GEO_PRESETS]
    if unknown_presets:
        blocked.append(f"unknown_geo_preset:{','.join(unknown_presets)}")
    if min_recurring_ads < 1:
        blocked.append("min_recurring_ads_must_be_positive")

    client = MetaMarketingClient()

    if blocked:
        return {
            "mission": "37W",
            "status": "blocked",
            "will_execute_real_action": False,
            "will_activate_spend": False,
            "network_access_used": False,
            "dry_run": client.dry_run,
            "query": query,
            "blocked_reasons": blocked,
            "candidates": [],
            "likely_winners": [],
        }

    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    any_live = False

    for preset in geo_presets:
        countries = GEO_PRESETS[preset]["countries"]
        try:
            raw = client.search_ad_library(search_terms=query, countries=countries, limit=limit_per_market)
        except MetaMarketingError as exc:
            errors.append(f"{preset}: {exc}")
            continue

        any_live = any_live or not raw.get("dry_run", client.dry_run)
        counts = Counter((item.get("page_name") or "desconhecido") for item in (raw.get("data") or []))
        for page_name, active_ads_found in counts.items():
            candidates.append(
                {
                    "geo_preset": preset,
                    "countries": countries,
                    "page_name": page_name,
                    "active_ads_found": active_ads_found,
                    "min_recurring_ads_threshold": min_recurring_ads,
                    "verdict": (
                        "likely_winner_by_recurrence"
                        if active_ads_found >= min_recurring_ads
                        else "insufficient_recurrence"
                    ),
                }
            )

    candidates.sort(key=lambda item: item["active_ads_found"], reverse=True)
    likely_winners = [item for item in candidates if item["verdict"] == "likely_winner_by_recurrence"]

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Market Scan: {query}",
            "niche": query or "sem_query",
            "campaign_stage": "37W",
            "outcome": "winners_found" if likely_winners else "no_winner_by_recurrence",
            "lesson": "Termômetro de recorrência conta variações de anúncio ativas por página nos mercados fortes e aplica o limiar definido pelo operador — nunca inventa métrica de venda.",
            "metrics": {
                "candidates": len(candidates),
                "likely_winners": len(likely_winners),
                "query": query,
                "min_recurring_ads": min_recurring_ads,
            },
        }
    )

    return {
        "mission": "37W",
        "status": "winners_found" if likely_winners else ("scan_ready" if candidates else "no_results"),
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": any_live,
        "dry_run": not any_live,
        "query": query,
        "geo_presets": geo_presets,
        "min_recurring_ads": min_recurring_ads,
        "candidates_count": len(candidates),
        "candidates": candidates,
        "likely_winners": likely_winners,
        "errors": errors,
        "heuristic_disclaimer": (
            f"Veredito 'likely_winner_by_recurrence' é uma HEURÍSTICA de negócio definida pelo operador "
            f"(>= {min_recurring_ads} variações de anúncio da mesma página ativas ao mesmo tempo no mercado). "
            "A Meta Ad Library API não informa vendas, receita ou lucro — apenas quantos anúncios estão "
            "ativos. Volume alto de anúncio é um indício de que o anunciante está reinvestindo porque "
            "está performando, não uma prova de faturamento."
        ),
        "recommended_next_step": (
            "para cada likely_winner, rodar /global-intelligence/ad-library-search-live com o page_name "
            "pra puxar o texto de criativo real e alimentar o winning-ad-score"
        ),
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
