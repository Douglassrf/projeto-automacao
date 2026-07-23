"""Mineracao REAL na Biblioteca de Anuncios do Facebook (Meta Ad Library API).

Fluxo completo do produto:
1. Pesquisa anuncios ATIVOS na Ad Library oficial (graph.facebook.com/ads_archive)
   por moeda: EUR, USD e BRL (mapeadas para paises correspondentes).
2. Agrupa por anunciante (page_id) e conta anuncios ativos.
3. Classifica os campeoes: >=15 BRONZE, >=20 PRATA, >=25 OURO.
4. Para o campeao, gera automaticamente:
   - anuncio remodelado (copy pronta para subir),
   - produto campeao + 5 produtos de subnicho do mesmo tema,
   - 5 sub-anuncios (um por subnicho),
   - site/landing page HTML completa com os 6 blocos de oferta.

Requer o token no ambiente: META_AD_LIBRARY_TOKEN (ou META_ACCESS_TOKEN).
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

import httpx

AD_LIBRARY_URL = "https://graph.facebook.com/v21.0/ads_archive"

CURRENCY_COUNTRIES: dict[str, list[str]] = {
    # Zona do euro completa (20 paises) + territorios franceses nas Americas
    # (Guiana Francesa, Guadalupe, Martinica)
    "EUR": [
        "FR", "DE", "ES", "IT", "PT", "NL", "BE", "AT", "IE", "GR",
        "FI", "SK", "SI", "LT", "LV", "EE", "LU", "MT", "CY", "HR",
        "GF", "GP", "MQ",
    ],
    # EUA + America Latina/Caribe dolarizados: Equador, El Salvador, Panama,
    # Porto Rico, Ilhas Virgens Americanas e Britanicas, Turks e Caicos
    "USD": ["US", "EC", "SV", "PA", "PR", "VI", "VG", "TC"],
    "BRL": ["BR"],
}

FIELDS = ",".join(
    [
        "id",
        "page_id",
        "page_name",
        "ad_creative_bodies",
        "ad_creative_link_titles",
        "ad_creative_link_descriptions",
        "ad_snapshot_url",
        "ad_delivery_start_time",
        "currency",
        "languages",
        "publisher_platforms",
    ]
)


def _get_token() -> str | None:
    return os.getenv("META_AD_LIBRARY_TOKEN") or os.getenv("META_ACCESS_TOKEN")


def classify(active_ads: int) -> str:
    if active_ads >= 25:
        return "OURO"
    if active_ads >= 20:
        return "PRATA"
    if active_ads >= 15:
        return "BRONZE"
    return "ABAIXO_DO_CORTE"


# Metodologia Renda em Dolar: corte de 15 ativos na LATAM/dolar/euro,
# mas no Brasil o mercado e mais sofisticado — corte sobe para 30.
MIN_ACTIVE_BY_CURRENCY = {"BRL": 30, "USD": 15, "EUR": 15}


def search_ad_library(
    search_terms: str,
    currency: str = "BRL",
    min_active_ads: int | None = None,
    limit: int = 200,
    countries: list[str] | None = None,
) -> dict[str, Any]:
    """Pesquisa real na Ad Library e classifica anunciantes campeoes."""
    if min_active_ads is None:
        min_active_ads = MIN_ACTIVE_BY_CURRENCY.get(currency.upper(), 15)
    token = _get_token()
    if not token:
        return {
            "status": "error",
            "error": "missing_token",
            "message": (
                "Configure META_AD_LIBRARY_TOKEN (ou META_ACCESS_TOKEN) nas variaveis "
                "de ambiente da Vercel para ativar a mineracao real."
            ),
        }

    currency = currency.upper()
    target_countries = countries or CURRENCY_COUNTRIES.get(currency)
    if not target_countries:
        return {
            "status": "error",
            "error": "invalid_currency",
            "message": f"Moeda '{currency}' nao suportada. Use EUR, USD ou BRL.",
        }

    params = {
        "search_terms": search_terms,
        "ad_type": "ALL",
        "ad_active_status": "ACTIVE",
        "ad_reached_countries": "[" + ",".join(f'"{c}"' for c in target_countries) + "]",
        "fields": FIELDS,
        "limit": min(limit, 300),
        "access_token": token,
    }

    ads: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=30) as client:
            url: str | None = AD_LIBRARY_URL
            query: dict[str, Any] | None = params
            for _ in range(5):  # ate 5 paginas
                resp = client.get(url, params=query)
                data = resp.json()
                if "error" in data:
                    return {
                        "status": "error",
                        "error": "meta_api_error",
                        "message": data["error"].get("message"),
                        "details": data["error"],
                    }
                ads.extend(data.get("data", []))
                next_url = data.get("paging", {}).get("next")
                if not next_url or len(ads) >= limit:
                    break
                url, query = next_url, None
    except httpx.HTTPError as exc:
        return {"status": "error", "error": "network_error", "message": str(exc)}

    by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ad in ads:
        by_page[str(ad.get("page_id"))].append(ad)

    champions = []
    for page_id, page_ads in by_page.items():
        count = len(page_ads)
        tier = classify(count)
        sample = page_ads[0]
        champions.append(
            {
                "page_id": page_id,
                "page_name": sample.get("page_name"),
                "active_ads": count,
                "classification": tier,
                "champion": tier != "ABAIXO_DO_CORTE" and count >= min_active_ads,
                "currency": currency,
                "sample_ad": {
                    "id": sample.get("id"),
                    "body": (sample.get("ad_creative_bodies") or [None])[0],
                    "title": (sample.get("ad_creative_link_titles") or [None])[0],
                    "snapshot_url": sample.get("ad_snapshot_url"),
                },
            }
        )
    champions.sort(key=lambda c: c["active_ads"], reverse=True)
    winners = [c for c in champions if c["champion"]]

    return {
        "status": "ok",
        "mode": "real_ad_library_api",
        "search_terms": search_terms,
        "currency": currency,
        "countries": target_countries,
        "min_active_ads": min_active_ads,
        "total_ads_scanned": len(ads),
        "total_advertisers": len(champions),
        "winners_found": len(winners),
        "winners": winners[:20],
        "all_advertisers": champions[:50],
    }


# ---------------------------------------------------------------------------
# DeepSeek (opcional): copywriting por IA quando DEEPSEEK_API_KEY estiver setada
# ---------------------------------------------------------------------------

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def _deepseek_key() -> str | None:
    # "chave" e o nome que a variavel recebeu no painel da Vercel
    return os.getenv("DEEPSEEK_API_KEY") or os.getenv("chave")


def deepseek_copy(prompt: str) -> str | None:
    """Chama a DeepSeek para gerar copy. Retorna None se nao houver chave ou em erro."""
    key = _deepseek_key()
    if not key:
        return None
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Voce e um copywriter de resposta direta especialista em "
                                "dropshipping e anuncios de Facebook em portugues do Brasil. "
                                "Responda APENAS com o texto pedido, sem explicacoes."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.8,
                    "max_tokens": 600,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Geracao automatica: anuncio remodelado + produtos + subnichos + site
# ---------------------------------------------------------------------------

SUBNICHE_ANGLES = [
    ("Iniciantes", "para quem esta comecando do zero"),
    ("Avancado", "versao premium para resultados maiores"),
    ("Kit Completo", "combo com tudo incluso e desconto"),
    ("Acessorio Essencial", "complemento indispensavel do produto principal"),
    ("Oferta Relampago", "edicao limitada com bonus exclusivo"),
]

CURRENCY_SYMBOL = {"BRL": "R$", "USD": "$", "EUR": "€"}


def remodel_ad(winner: dict[str, Any], product_name: str) -> dict[str, Any]:
    base_body = (winner.get("sample_ad") or {}).get("body") or ""
    ai = deepseek_copy(
        f"Produto: {product_name}. Anuncio campeao de referencia (remodele sem copiar): "
        f"'{base_body[:500]}'. Gere no formato exato:\nHEADLINE: ...\nTEXTO: ...\nCTA: ..."
    )
    if ai:
        parts = {"HEADLINE": "", "TEXTO": "", "CTA": ""}
        for line in ai.splitlines():
            for k in parts:
                if line.upper().startswith(k):
                    parts[k] = line.split(":", 1)[-1].strip()
        if parts["HEADLINE"] and parts["TEXTO"]:
            return {
                "headline": parts["HEADLINE"],
                "primary_text": parts["TEXTO"],
                "cta": parts["CTA"] or "Comprar agora",
                "generated_by": "deepseek",
                "inspiration_source": base_body[:280],
                "advertiser_reference": winner.get("page_name"),
            }
    return {
        "generated_by": "template",
        "headline": f"{product_name}: o queridinho do momento chegou",
        "primary_text": (
            f"Milhares de pessoas ja garantiram o {product_name}. "
            "Estoque limitado + frete rapido. Toque em Saiba Mais e veja por que "
            "todo mundo esta falando disso."
        ),
        "cta": "Comprar agora",
        "inspiration_source": base_body[:280],
        "advertiser_reference": winner.get("page_name"),
    }


def generate_products(product_name: str, currency: str) -> list[dict[str, Any]]:
    sym = CURRENCY_SYMBOL.get(currency, "R$")
    products = [
        {
            "role": "campeao",
            "name": product_name,
            "price": f"{sym} 97,00",
            "pitch": f"{product_name} — o produto validado com dezenas de anuncios ativos.",
        }
    ]
    for i, (angle, desc) in enumerate(SUBNICHE_ANGLES, start=1):
        products.append(
            {
                "role": f"subnicho_{i}",
                "name": f"{product_name} {angle}",
                "price": f"{sym} {47 + i * 10},00",
                "pitch": f"{product_name} {angle}: {desc}.",
            }
        )
    return products


def generate_sub_ads(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "product": p["name"],
            "headline": f"{p['name']} por {p['price']}",
            "primary_text": f"{p['pitch']} Aproveite enquanto dura.",
            "cta": "Saiba mais",
        }
        for p in products
        if p["role"] != "campeao"
    ]


def build_site_html(product_name: str, products: list[dict[str, Any]], main_ad: dict[str, Any]) -> str:
    cards = "".join(
        f"""
        <div class="card{' hero' if p['role'] == 'campeao' else ''}">
          <span class="badge">{'PRODUTO CAMPEAO' if p['role'] == 'campeao' else 'OFERTA RELACIONADA'}</span>
          <h3>{p['name']}</h3>
          <p>{p['pitch']}</p>
          <div class="price">{p['price']}</div>
          <a class="btn" href="#checkout">Comprar agora</a>
        </div>"""
        for p in products
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{product_name} — Oferta Oficial</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; font-family: 'Segoe UI', Arial, sans-serif; }}
  body {{ background:#0f1115; color:#eee; }}
  header {{ padding:48px 16px; text-align:center; background:linear-gradient(135deg,#1a1f2e,#0f1115); }}
  header h1 {{ font-size:2.2rem; margin-bottom:12px; }}
  header p {{ color:#9aa4b2; max-width:640px; margin:0 auto 24px; }}
  .btn {{ display:inline-block; background:#22c55e; color:#04110a; font-weight:700; padding:14px 32px; border-radius:8px; text-decoration:none; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; max-width:1100px; margin:32px auto; padding:0 16px; }}
  .card {{ background:#1a1f2e; border-radius:12px; padding:24px; }}
  .card.hero {{ grid-column:1/-1; border:2px solid #22c55e; }}
  .badge {{ font-size:.7rem; letter-spacing:.1em; color:#22c55e; }}
  .price {{ font-size:1.6rem; font-weight:800; margin:12px 0; }}
  footer {{ text-align:center; padding:32px; color:#556; font-size:.8rem; }}
</style>
</head>
<body>
<header>
  <h1>{main_ad['headline']}</h1>
  <p>{main_ad['primary_text']}</p>
  <a class="btn" href="#checkout">{main_ad['cta']}</a>
</header>
<section class="grid">{cards}
</section>
<footer>Oferta por tempo limitado. Site gerado automaticamente pelo AdIntelligence Pro.</footer>
</body>
</html>"""


def run_full_pipeline(
    search_terms: str,
    currency: str = "BRL",
    min_active_ads: int = 15,
    product_name: str | None = None,
) -> dict[str, Any]:
    """Pipeline completo: minera -> classifica -> remodela -> gera produtos/sub-anuncios/site."""
    mining = search_ad_library(search_terms, currency=currency, min_active_ads=min_active_ads)
    if mining.get("status") != "ok":
        return mining
    if not mining["winners"]:
        return {
            "status": "ok",
            "winners_found": 0,
            "message": (
                f"Nenhum anunciante com {min_active_ads}+ anuncios ativos para "
                f"'{search_terms}' em {currency}. Tente outro termo ou reduza o corte."
            ),
            "mining": mining,
        }

    winner = mining["winners"][0]
    name = product_name or search_terms.title()
    main_ad = remodel_ad(winner, name)
    products = generate_products(name, currency.upper())
    sub_ads = generate_sub_ads(products)
    site_html = build_site_html(name, products, main_ad)

    return {
        "status": "ok",
        "mode": "real_pipeline",
        "winner": winner,
        "main_ad": main_ad,
        "sub_ads": sub_ads,
        "products": products,
        "site_html": site_html,
        "mining_summary": {
            "total_ads_scanned": mining["total_ads_scanned"],
            "winners_found": mining["winners_found"],
            "currency": mining["currency"],
            "countries": mining["countries"],
        },
    }
