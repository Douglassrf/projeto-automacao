"""Mineracao REAL na Biblioteca de Anuncios do Facebook (Meta Ad Library API).

VERSAO CORRIGIDA — 3 bugs resolvidos:

  BUG 1 (CRITICO): o fallback de token engolia o erro real.
      Antes: se o 1o token falhasse com code 190, o codigo trocava para o
      proximo e devolvia o erro DESSE, escondendo o motivo verdadeiro.
      Agora: cada tentativa e registrada e devolvida em `attempts`.

  BUG 2: /status mentia dizendo "pronto para minerar" so porque a variavel
      de ambiente existia, sem nunca validar o token contra a Meta.
      Agora: validate_token() faz uma chamada real e diz a verdade.

  BUG 3: os "5 subnichos" eram sufixos fixos ("Iniciantes", "Avancado"...)
      colados em qualquer produto. Nao eram temas relevantes.
      Agora: gerados por IA a partir do anuncio minerado, com o template
      antigo apenas como rede de seguranca.

Requer o token no ambiente. Nomes aceitos, em ordem: ver TOKEN_ENV_NAMES.

IMPORTANTE: a Ad Library API (ads_archive) NAO aceita token de Usuario do
Sistema. Exige token de USUARIO com identidade confirmada e o app aprovado
para acesso a Ad Library.
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

import httpx

AD_LIBRARY_URL = "https://graph.facebook.com/v21.0/ads_archive"

# Ordem de preferencia. Mantidos os nomes historicos do painel da Vercel
# para nao quebrar nada, mas o nome canonico e META_AD_LIBRARY_TOKEN.
TOKEN_ENV_NAMES = [
    "META_AD_LIBRARY_TOKEN",
    "META_ACCESS_TOKEN",
    "chaveee",
]

CURRENCY_COUNTRIES: dict[str, list[str]] = {
    "EUR": [
        "FR", "DE", "ES", "IT", "PT", "NL", "BE", "AT", "IE", "GR",
        "FI", "SK", "SI", "LT", "LV", "EE", "LU", "MT", "CY", "HR",
        "GF", "GP", "MQ",
    ],
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


# ---------------------------------------------------------------------------
# Tokens — BUG 1 e BUG 2
# ---------------------------------------------------------------------------

# Valores usados como marcador de "desativado". Nao sao tokens.
_PLACEHOLDERS = {"", "DESATIVADO", "DESATIVADO_PARA_DIAGNOSTICO", "DISABLED", "NONE"}


def _token_candidates() -> list[tuple[str, str]]:
    """Retorna [(nome_da_variavel, valor)] dos tokens disponiveis, sem duplicar."""
    found: list[tuple[str, str]] = []
    seen_values: set[str] = set()
    for name in TOKEN_ENV_NAMES:
        value = (os.getenv(name) or "").strip()
        if not value or value.upper() in _PLACEHOLDERS:
            continue
        if value in seen_values:
            continue
        seen_values.add(value)
        found.append((name, value))
    return found


def _get_token() -> str | None:
    candidates = _token_candidates()
    return candidates[0][1] if candidates else None


def validate_token(token: str | None = None) -> dict[str, Any]:
    """Valida um token DE VERDADE contra a Meta. Usar no /status.

    Faz a consulta mais barata possivel (limit=1) so para saber se o token
    e aceito pelo endpoint que a gente realmente usa.
    """
    if token is None:
        token = _get_token()
    if not token:
        return {
            "valid": False,
            "reason": "missing_token",
            "message": (
                "Nenhum token configurado. Defina META_AD_LIBRARY_TOKEN nas "
                "variaveis de ambiente."
            ),
        }
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                AD_LIBRARY_URL,
                params={
                    "search_terms": "teste",
                    "ad_type": "ALL",
                    "ad_reached_countries": '["BR"]',
                    "limit": 1,
                    "access_token": token,
                },
            )
            data = resp.json()
    except httpx.HTTPError as exc:
        return {"valid": False, "reason": "network_error", "message": str(exc)}

    if "error" in data:
        err = data["error"]
        code = err.get("code")
        hint = None
        if code == 190:
            hint = (
                "Token invalido ou expirado. Lembre-se: a Ad Library API NAO "
                "aceita token de Usuario do Sistema — precisa ser token de "
                "USUARIO, com identidade confirmada."
            )
        elif code in (10, 200, 803):
            hint = (
                "O app provavelmente nao tem acesso liberado a Ad Library API. "
                "Verifique App Review e confirmacao de identidade."
            )
        return {
            "valid": False,
            "reason": "meta_api_error",
            "code": code,
            "message": err.get("message"),
            "hint": hint,
            "details": err,
        }

    return {"valid": True, "reason": "ok", "message": "Token aceito pela Ad Library."}


def token_status() -> dict[str, Any]:
    """Resumo honesto para o endpoint /status."""
    candidates = _token_candidates()
    if not candidates:
        return {
            "token_configured": False,
            "token_valid": False,
            "source": None,
            "message": "Nenhum token configurado.",
        }
    name, value = candidates[0]
    check = validate_token(value)
    return {
        "token_configured": True,
        "token_valid": check["valid"],
        "source": name,
        "candidates_available": [n for n, _ in candidates],
        "message": check.get("message"),
        "hint": check.get("hint"),
    }


def classify(active_ads: int) -> str:
    if active_ads >= 25:
        return "OURO"
    if active_ads >= 20:
        return "PRATA"
    if active_ads >= 15:
        return "BRONZE"
    return "ABAIXO_DO_CORTE"


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

    candidates = _token_candidates()
    if not candidates:
        return {
            "status": "error",
            "error": "missing_token",
            "message": (
                "Configure META_AD_LIBRARY_TOKEN nas variaveis de ambiente da "
                "Vercel para ativar a mineracao real."
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

    base_params = {
        "search_terms": search_terms,
        "ad_type": "ALL",
        "ad_active_status": "ACTIVE",
        "ad_reached_countries": "[" + ",".join(f'"{c}"' for c in target_countries) + "]",
        "fields": FIELDS,
        "limit": min(limit, 300),
    }

    # BUG 1 CORRIGIDO: tenta cada token e GUARDA o resultado de cada tentativa.
    # Nada de erro silencioso: se todos falharem, devolvemos a lista completa.
    attempts: list[dict[str, Any]] = []

    for token_name, token_value in candidates:
        ads: list[dict[str, Any]] = []
        params = {**base_params, "access_token": token_value}
        failed: dict[str, Any] | None = None

        try:
            with httpx.Client(timeout=30) as client:
                url: str | None = AD_LIBRARY_URL
                query: dict[str, Any] | None = params
                for _ in range(5):  # ate 5 paginas
                    resp = client.get(url, params=query)
                    data = resp.json()
                    if "error" in data:
                        failed = {
                            "token_source": token_name,
                            "code": data["error"].get("code"),
                            "message": data["error"].get("message"),
                            "details": data["error"],
                        }
                        break
                    ads.extend(data.get("data", []))
                    next_url = data.get("paging", {}).get("next")
                    if not next_url or len(ads) >= limit:
                        break
                    url, query = next_url, None
        except httpx.HTTPError as exc:
            failed = {
                "token_source": token_name,
                "code": "network_error",
                "message": str(exc),
            }

        if failed:
            attempts.append(failed)
            continue  # tenta o proximo token, mas SEM apagar o erro deste

        return _summarize(ads, search_terms, currency, target_countries,
                          min_active_ads, token_name, attempts)

    # Todos os tokens falharam — devolve tudo, sem mascarar nada.
    return {
        "status": "error",
        "error": "meta_api_error",
        "message": attempts[0]["message"] if attempts else "Falha desconhecida.",
        "tokens_tried": len(attempts),
        "attempts": attempts,
        "hint": (
            "Se o code for 190 em todas as tentativas: a Ad Library API nao "
            "aceita token de Usuario do Sistema. Gere um token de USUARIO no "
            "Graph API Explorer e estenda para 60 dias no Access Token Debugger."
        ),
    }


def _summarize(ads, search_terms, currency, target_countries, min_active_ads,
               token_source, attempts) -> dict[str, Any]:
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
        "token_source": token_source,
        "failed_attempts": attempts,  # transparencia: o que foi tentado antes
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
# DeepSeek
# ---------------------------------------------------------------------------

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def _deepseek_key() -> str | None:
    return os.getenv("DEEPSEEK_API_KEY") or os.getenv("chave")


def deepseek_copy(prompt: str, max_tokens: int = 600) -> str | None:
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
                    "max_tokens": max_tokens,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Geracao: anuncio remodelado + produtos + subnichos + site
# ---------------------------------------------------------------------------

# Rede de seguranca apenas. NAO e mais o caminho principal.
FALLBACK_ANGLES = [
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


def generate_subniches(product_name: str, ad_body: str = "") -> list[tuple[str, str]]:
    """BUG 3 CORRIGIDO: subnichos REAIS, extraidos do anuncio minerado.

    Pede a IA cinco produtos complementares que o MESMO comprador compraria
    depois — que e exatamente o objetivo do projeto. So cai no template fixo
    se a IA estiver indisponivel.
    """
    ai = deepseek_copy(
        f"Produto principal: '{product_name}'.\n"
        f"Anuncio campeao que o vende: '{ad_body[:600]}'.\n\n"
        "Liste 5 produtos de SUBNICHO que a MESMA pessoa que comprou o produto "
        "principal compraria em seguida. Devem ser produtos complementares e "
        "especificos do tema — nao variacoes genericas do mesmo item.\n"
        "Formato exato, uma por linha, sem numeracao:\n"
        "NOME | beneficio em ate 12 palavras",
        max_tokens=400,
    )
    if ai:
        out: list[tuple[str, str]] = []
        for line in ai.splitlines():
            if "|" not in line:
                continue
            nome, _, pitch = line.partition("|")
            nome, pitch = nome.strip(" -•\t"), pitch.strip()
            if nome and pitch:
                out.append((nome, pitch))
        if len(out) >= 3:
            return out[:5]
    return FALLBACK_ANGLES


def generate_products(
    product_name: str, currency: str, ad_body: str = ""
) -> list[dict[str, Any]]:
    sym = CURRENCY_SYMBOL.get(currency, "R$")
    products = [
        {
            "role": "campeao",
            "name": product_name,
            "price": f"{sym} 97,00",
            "pitch": f"{product_name} — o produto validado com dezenas de anuncios ativos.",
        }
    ]
    subniches = generate_subniches(product_name, ad_body)
    ai_generated = subniches is not FALLBACK_ANGLES
    for i, (nome, pitch) in enumerate(subniches, start=1):
        products.append(
            {
                "role": f"subnicho_{i}",
                "name": nome if ai_generated else f"{product_name} {nome}",
                "price": f"{sym} {47 + i * 10},00",
                "pitch": pitch if ai_generated else f"{product_name} {nome}: {pitch}.",
                "generated_by": "deepseek" if ai_generated else "template",
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


def build_site_html(
    product_name: str,
    products: list[dict[str, Any]],
    main_ad: dict[str, Any],
    checkout_url: str = "#checkout",
) -> str:
    cards = "".join(
        f"""
        <div class="card{' hero' if p['role'] == 'campeao' else ''}">
          <span class="badge">{'PRODUTO CAMPEAO' if p['role'] == 'campeao' else 'OFERTA RELACIONADA'}</span>
          <h3>{p['name']}</h3>
          <p>{p['pitch']}</p>
          <div class="price">{p['price']}</div>
          <a class="btn" href="{checkout_url}">Comprar agora</a>
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
  <a class="btn" href="{checkout_url}">{main_ad['cta']}</a>
</header>
<section class="grid">{cards}
</section>
<footer>Oferta por tempo limitado. Site gerado automaticamente pelo AdIntelligence Pro.</footer>
</body>
</html>"""


def run_full_pipeline(
    search_terms: str,
    currency: str = "BRL",
    min_active_ads: int | None = None,
    product_name: str | None = None,
    checkout_url: str = "#checkout",
) -> dict[str, Any]:
    """Pipeline completo: minera -> classifica -> remodela -> produtos/sub-anuncios/site."""
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
    ad_body = (winner.get("sample_ad") or {}).get("body") or ""
    main_ad = remodel_ad(winner, name)
    products = generate_products(name, currency.upper(), ad_body=ad_body)
    sub_ads = generate_sub_ads(products)
    site_html = build_site_html(name, products, main_ad, checkout_url=checkout_url)

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
            "token_source": mining.get("token_source"),
        },
    }
