"""Motor de distribuicao multiplataforma.

Pega o conteudo campeao gerado pela pesquisa (Facebook Ads Library / TikTok
Creative Center) e replica ADAPTADO para cada plataforma — mesmo video 9:16,
mas copy, titulo, hashtags e tom nativos de cada rede. O que muda por rede:

- YouTube Shorts: titulo SEO + descricao com keywords + tags (busca importa)
- LinkedIn: tom profissional/negocios, storytelling de empreendedorismo
- X (Twitter): thread curta e direta, gancho polemico/curioso
- Snapchat: linguagem jovem, urgencia, AR-friendly
- Kwai: portugues popular brasileiro, apelo emocional direto (publico classe C/D)

A publicacao automatica em cada rede exige token proprio (YouTube Data API,
LinkedIn API, X API, Snap/Kwai Ads) — enquanto nao configurados, o motor
entrega o pacote pronto para colar em cada plataforma.
"""

from __future__ import annotations

import os
from typing import Any

from app.services.ad_library_real import deepseek_copy

PLATFORMS: dict[str, dict[str, str]] = {
    "youtube_shorts": {
        "nome": "YouTube Shorts",
        "formato": "9:16, ate 60s, mesmo video do TikTok (sem marca dagua)",
        "tom": "titulo SEO com keyword do produto + curiosidade; descricao com 3 keywords; 5-8 tags",
        "token_env": "YOUTUBE_API_KEY",
    },
    "linkedin": {
        "nome": "LinkedIn",
        "formato": "video 9:16 ou 1:1, post de texto forte acima do video",
        "tom": "profissional: historia de negocio/empreendedorismo por tras do produto, sem girias, CTA sutil",
        "token_env": "LINKEDIN_ACCESS_TOKEN",
    },
    "x_twitter": {
        "nome": "X (Twitter)",
        "formato": "video ate 2:20, tweet de gancho + 2-3 replies em thread",
        "tom": "direto, curioso ou polemico construtivo; frases curtas; 1-2 hashtags no maximo",
        "token_env": "X_API_KEY",
    },
    "snapchat": {
        "nome": "Snapchat",
        "formato": "9:16 fullscreen, primeiros 2s decisivos",
        "tom": "linguagem jovem, urgencia e FOMO, emojis, CTA de swipe up",
        "token_env": "SNAPCHAT_ACCESS_TOKEN",
    },
    "kwai": {
        "nome": "Kwai",
        "formato": "9:16, ate 57s, mesmo video do TikTok",
        "tom": "portugues popular brasileiro, apelo emocional direto, precos e desconto em destaque, prova social calorosa",
        "token_env": "KWAI_ACCESS_TOKEN",
    },
}


def distribute(
    product: str,
    source_script: str,
    source_platform: str = "tiktok",
    landing_url: str = "",
    language: str = "pt-BR",
) -> dict[str, Any]:
    """Gera o pacote de publicacao adaptado para cada plataforma."""
    result: dict[str, Any] = {
        "status": "ok",
        "product": product,
        "source": source_platform,
        "video_note": "Use o MESMO video 9:16 gerado pelo render-premium (sem marca dagua) em todas.",
        "platforms": {},
    }
    for key, p in PLATFORMS.items():
        prompt = (
            f"Voce e um social media senior. Produto: {product}. Idioma: {language}. "
            f"Link da oferta: {landing_url or '[LINK]'}. "
            f"Conteudo campeao original (minerado no {source_platform}): '{source_script[:600]}'. "
            f"Adapte para {p['nome']} — formato: {p['formato']} — tom: {p['tom']}. "
            "Responda APENAS com o conteudo pronto para publicar (titulo/legenda/hashtags conforme a rede), sem explicacoes."
        )
        copy = deepseek_copy(prompt)
        token_ok = os.getenv(p["token_env"]) is not None
        result["platforms"][key] = {
            "nome": p["nome"],
            "formato": p["formato"],
            "conteudo": copy or f"[DEEPSEEK_API_KEY ausente] Adaptar manualmente com tom: {p['tom']}",
            "engine": "deepseek" if copy else "template",
            "publicacao_automatica": "ativa" if token_ok else f"pendente (configurar {p['token_env']})",
        }
    return result
