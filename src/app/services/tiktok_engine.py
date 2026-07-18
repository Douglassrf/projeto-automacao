"""Motor TikTok: mineracao de produtos campeoes + remodelagem de video + V1/V2/V3.

Mesmo padrao do motor Meta (ad_library_real.py):
1. Mineracao dos anuncios/produtos campeoes no TikTok Creative Center (Top Ads)
   por regiao: BR, US e Europa. Usa a API oficial do TikTok for Business quando
   TIKTOK_ACCESS_TOKEN estiver configurado.
2. Classificacao por forca do anuncio (curtidas/CTR/tempo ativo):
   BRONZE / PRATA / OURO.
3. Remodelagem do video campeao: roteiro cena a cena (hook, prova, oferta, CTA)
   pronto para gravar/editar, gerado por DeepSeek quando disponivel.
4. Anuncio pronto + escada V1 (descoberta) / V2 (validacao) / V3 (campeao)
   com as regras proprias do TikTok (criativo satura mais rapido que no Meta).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.services.ad_library_real import deepseek_copy

TIKTOK_TOP_ADS_URL = "https://business-api.tiktok.com/open_api/v1.3/creative/top_ads/search/"

REGION_MAP: dict[str, list[str]] = {
    "BR": ["BR"],
    "US": ["US"],
    "EU": ["FR", "DE", "ES", "IT", "PT", "NL"],
}


def _get_token() -> str | None:
    return os.getenv("TIKTOK_ACCESS_TOKEN")


def classify_tiktok(like_count: int, days_active: int) -> str:
    score = like_count / 1000 + days_active * 2
    if score >= 100:
        return "OURO"
    if score >= 50:
        return "PRATA"
    if score >= 20:
        return "BRONZE"
    return "ABAIXO_DO_CORTE"


def mine_top_ads(keyword: str, region: str = "BR", limit: int = 50) -> dict[str, Any]:
    """Mineracao real no Top Ads do TikTok Creative Center (API oficial)."""
    token = _get_token()
    if not token:
        return {
            "status": "error",
            "error": "missing_token",
            "message": (
                "Configure TIKTOK_ACCESS_TOKEN nas variaveis da Vercel. Gere em "
                "business-api.tiktok.com (TikTok for Business -> criar app de developer)."
            ),
        }
    region = region.upper()
    countries = REGION_MAP.get(region)
    if not countries:
        return {"status": "error", "error": "invalid_region", "message": "Use BR, US ou EU."}

    ads: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=30) as client:
            for country in countries:
                resp = client.get(
                    TIKTOK_TOP_ADS_URL,
                    headers={"Access-Token": token},
                    params={"keyword": keyword, "country_code": country, "limit": min(limit, 50), "order_by": "like"},
                )
                data = resp.json()
                if data.get("code") not in (0, None):
                    return {
                        "status": "error",
                        "error": "tiktok_api_error",
                        "message": data.get("message"),
                        "details": data,
                    }
                for item in (data.get("data") or {}).get("list") or []:
                    ads.append({"country": country, **item})
    except httpx.HTTPError as exc:
        return {"status": "error", "error": "network_error", "message": str(exc)}

    winners = []
    for ad in ads:
        likes = int(ad.get("like") or ad.get("like_count") or 0)
        days = int(ad.get("duration_days") or ad.get("days_active") or 0)
        tier = classify_tiktok(likes, days)
        winners.append(
            {
                "ad_title": ad.get("ad_title") or ad.get("title"),
                "brand_name": ad.get("brand_name"),
                "country": ad.get("country"),
                "likes": likes,
                "days_active": days,
                "classification": tier,
                "champion": tier != "ABAIXO_DO_CORTE",
                "video_url": ad.get("video_info", {}).get("video_url") if isinstance(ad.get("video_info"), dict) else ad.get("video_url"),
                "landing_page": ad.get("landing_page"),
            }
        )
    winners.sort(key=lambda w: w["likes"], reverse=True)
    champions = [w for w in winners if w["champion"]]

    return {
        "status": "ok",
        "mode": "real_tiktok_top_ads",
        "keyword": keyword,
        "region": region,
        "countries": countries,
        "total_ads_scanned": len(ads),
        "winners_found": len(champions),
        "winners": champions[:20],
    }


# ---------------------------------------------------------------------------
# Remodelagem de video: roteiro cena a cena pronto para gravar/editar
# ---------------------------------------------------------------------------

def remodel_video_script(product_name: str, winner: dict[str, Any] | None = None) -> dict[str, Any]:
    reference = (winner or {}).get("ad_title") or ""
    ai = deepseek_copy(
        f"Produto: {product_name}. Video campeao de referencia no TikTok: '{reference}'. "
        "Crie um roteiro de video de TikTok Ads de 25-35 segundos, remodelado (sem copiar), no formato exato:\n"
        "HOOK (0-3s): ...\nPROBLEMA (3-8s): ...\nDEMONSTRACAO (8-18s): ...\nPROVA (18-25s): ...\nOFERTA+CTA (25-35s): ...\nTEXTO_NA_TELA: ...\nAUDIO: ..."
    )
    if ai:
        return {"generated_by": "deepseek", "script": ai, "duration_seconds": 35, "format": "9:16 vertical"}
    return {
        "generated_by": "template",
        "format": "9:16 vertical",
        "duration_seconds": 35,
        "script": {
            "hook_0_3s": f"Pare de rolar! Voce precisa ver o que esse {product_name} faz...",
            "problema_3_8s": "Mostre o problema do dia a dia que o produto resolve (close no rosto frustrado).",
            "demonstracao_8_18s": f"Demonstre o {product_name} em uso real, 3 angulos rapidos, cortes a cada 2s.",
            "prova_18_25s": "Mostre resultado antes/depois + print de avaliacao 5 estrelas.",
            "oferta_cta_25_35s": "Hoje com desconto + frete rapido. Toque no botao e garanta o seu!",
            "texto_na_tela": f"{product_name} VIRAL ✨ | 50% OFF SO HOJE",
            "audio": "Trending sound do momento (verificar biblioteca comercial do TikTok Ads).",
        },
    }


def build_ready_ad(product_name: str, region: str, script: dict[str, Any]) -> dict[str, Any]:
    return {
        "ad_name": f"{product_name} | TikTok | {region} | V1",
        "objective": "Conversions (Complete Payment)",
        "placement": "TikTok only, video 9:16",
        "ad_text": f"O {product_name} que esta viralizando 🔥 Desconto so hoje + frete rapido. Toque e garanta!",
        "cta_button": "Comprar agora",
        "video_script": script,
        "spark_ads": "Recomendado: publicar como Spark Ad (perfil real) para mais confianca.",
    }


# ---------------------------------------------------------------------------
# Escada V1/V2/V3 do TikTok
# ---------------------------------------------------------------------------

TIKTOK_STAGES = {
    "V1": {
        "goal": "descoberta",
        "budget_brl_dia": 30,
        "setup": "1 campanha, 1 grupo de anuncio amplo (sem interesse), 3 videos diferentes",
        "kpis": {"ctr_min_pct": 1.0, "cpm_teto_brl": 25, "hook_rate_min_pct": 30},
        "regra": "TikTok exige orcamento minimo de grupo (~R$30/dia). Rodar 3 dias sem mexer.",
        "next_if_positive": "V2",
    },
    "V2": {
        "goal": "validacao",
        "budget_brl_dia": 60,
        "setup": "Duplicar o grupo com o melhor video, manter amplo, adicionar 2 variacoes de hook",
        "kpis": {"cpa_meta": "definir", "checkout_rate_min_pct": 15, "roas_min": 1.2},
        "regra": "Nao editar o grupo original. Criativo no TikTok satura em 5-7 dias: ja preparar proximos videos.",
        "next_if_positive": "V3",
    },
    "V3": {
        "goal": "selecionar campeao e escalar inicio",
        "budget_brl_dia": 100,
        "setup": "Campanha CBO com os 2 melhores videos + Spark Ads; desligar perdedores",
        "kpis": {"roas_min": 1.5, "frequency_teto": 2.5},
        "regra": "Aumentos de no maximo +20%/24h (mesma protecao do motor Meta V4). Renovar criativo toda semana.",
        "next_if_positive": "V4 (usar /scale/v4 com as metricas)",
    },
}


def run_tiktok_pipeline(
    keyword: str,
    region: str = "BR",
    product_name: str | None = None,
) -> dict[str, Any]:
    """Pipeline completo TikTok: minera -> classifica -> remodela video -> anuncio pronto -> escada V1-V3."""
    mining = mine_top_ads(keyword, region=region)
    winner = None
    if mining.get("status") == "ok" and mining.get("winners"):
        winner = mining["winners"][0]

    name = product_name or keyword.title()
    script = remodel_video_script(name, winner)
    ready_ad = build_ready_ad(name, region.upper(), script)

    return {
        "status": "ok" if mining.get("status") == "ok" else "partial",
        "mining": mining,
        "winner": winner,
        "video_remodelado": script,
        "anuncio_pronto": ready_ad,
        "escada_v1_v2_v3": TIKTOK_STAGES,
        "note": (
            None
            if mining.get("status") == "ok"
            else "Mineracao real pendente de TIKTOK_ACCESS_TOKEN; video e anuncio gerados mesmo assim."
        ),
    }
