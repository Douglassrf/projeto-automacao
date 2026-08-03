"""Rotas do modo REAL: mineracao na Ad Library + pipeline completo.

VERSAO CORRIGIDA — o cron estava travado em BRL.

MOTIVO DA MUDANCA (confirmado em facebook.com/ads/library/api):
A Ad Library API so devolve anuncios COMERCIAIS veiculados no Reino Unido e
na Uniao Europeia. Para qualquer outro pais ela devolve apenas anuncios de
temas sociais, eleicoes e politica.

O cron rodava com currency="BRL" chumbado no codigo. Mesmo com token e
permissao perfeitos, ele NUNCA encontraria um anuncio de dropshipping —
estava pedindo a Meta exatamente a categoria que ela nao entrega para o BR.

Agora a moeda do cron e configuravel e o padrao e EUR.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.services import ad_library_real

router = APIRouter(prefix="/real-mining", tags=["Real Mining - Ad Library"])

_last_pipeline: dict = {}

# Nichos que o cron diario garimpa. Configuravel por env var (lista separada
# por virgula) para mudar sem precisar de deploy de codigo.
DEFAULT_DAILY_NICHES: list[str] = [
    n.strip()
    for n in os.getenv("DEFAULT_DAILY_NICHES", "emagrecer,massageador,dor nas costas").split(",")
    if n.strip()
]

# EUR e o padrao porque e a unica zona onde a API devolve anuncio comercial.
# GBP tambem funciona (Reino Unido). BRL/USD so devolvem politico — nao use.
DEFAULT_DAILY_CURRENCY: str = os.getenv("DEFAULT_DAILY_CURRENCY", "EUR").upper()
DEFAULT_MIN_ACTIVE_ADS: int = int(os.getenv("DEFAULT_MIN_ACTIVE_ADS", "15"))

# Moedas que realmente rendem anuncio comercial na API.
COMMERCIAL_CURRENCIES = {"EUR", "GBP"}


class MiningRequest(BaseModel):
    search_terms: str = Field(..., min_length=2, description="Termo do produto/nicho")
    currency: str = Field("EUR", description="EUR ou GBP (comercial). BRL/USD so retornam politico.")
    min_active_ads: int = Field(15, ge=1, le=100)
    limit: int = Field(200, ge=10, le=300)


class PipelineRequest(MiningRequest):
    product_name: str | None = None
    checkout_url: str = "#checkout"


def _currency_warning(currency: str) -> str | None:
    if currency.upper() not in COMMERCIAL_CURRENCIES:
        return (
            f"AVISO: '{currency.upper()}' so retorna anuncios de temas sociais, "
            "eleicoes e politica. A Ad Library API expoe anuncios comerciais "
            "apenas para Reino Unido e Uniao Europeia. Use EUR ou GBP."
        )
    return None


@router.get("/status")
def status():
    # Agora valida o token DE VERDADE contra a Meta, em vez de so checar
    # se a variavel de ambiente existe.
    tok = ad_library_real.token_status()
    return {
        "status": "ok",
        "mode": "real",
        **tok,
        "deepseek_configured": ad_library_real._deepseek_key() is not None,
        "copywriter": "deepseek" if ad_library_real._deepseek_key() else "template",
        "currencies": list(ad_library_real.CURRENCY_COUNTRIES.keys()),
        "commercial_currencies": sorted(COMMERCIAL_CURRENCIES),
        "classification": {"BRONZE": "15+", "PRATA": "20+", "OURO": "25+"},
        "daily_cron": {
            "enabled": True,
            "niches": DEFAULT_DAILY_NICHES,
            "currency": DEFAULT_DAILY_CURRENCY,
            "min_active_ads": DEFAULT_MIN_ACTIVE_ADS,
            "schedule": "todo dia as 09:00 (America/Sao_Paulo)",
        },
    }


@router.post("/search")
def search(payload: MiningRequest):
    result = ad_library_real.search_ad_library(
        payload.search_terms,
        currency=payload.currency,
        min_active_ads=payload.min_active_ads,
        limit=payload.limit,
    )
    warn = _currency_warning(payload.currency)
    return {**result, "warning": warn} if warn else result


@router.post("/pipeline")
def pipeline(payload: PipelineRequest):
    global _last_pipeline
    result = ad_library_real.run_full_pipeline(
        payload.search_terms,
        currency=payload.currency,
        min_active_ads=payload.min_active_ads,
        product_name=payload.product_name,
        checkout_url=payload.checkout_url,
    )
    if result.get("status") == "ok" and result.get("site_html"):
        _last_pipeline = result
        result = {**result, "site_html": "gerado - abra GET /api/v1/real-mining/site"}
    warn = _currency_warning(payload.currency)
    return {**result, "warning": warn} if warn else result


@router.get("/cron-daily")
def cron_daily(request: Request):
    """Disparo automatico diario da mineracao de anuncios campeao.

    CORRIGIDO: moeda vem de DEFAULT_DAILY_CURRENCY (padrao EUR), nao mais
    chumbada em BRL. Os criterios de campeao continuam identicos:
    15+ BRONZE / 20+ PRATA / 25+ OURO, com corte em DEFAULT_MIN_ACTIVE_ADS.
    """
    expected_secret = os.environ.get("CRON_SECRET")
    if expected_secret:
        auth_header = request.headers.get("authorization", "")
        if auth_header != f"Bearer {expected_secret}":
            return {"status": "unauthorized"}

    global _last_pipeline
    runs = []
    for niche in DEFAULT_DAILY_NICHES:
        try:
            result = ad_library_real.run_full_pipeline(
                niche,
                currency=DEFAULT_DAILY_CURRENCY,
                min_active_ads=DEFAULT_MIN_ACTIVE_ADS,
                product_name=niche,
            )
            if result.get("status") == "ok" and result.get("site_html"):
                _last_pipeline = result
                result = {**result, "site_html": "gerado - abra GET /api/v1/real-mining/site"}
            runs.append({"niche": niche, "result": result})
        except Exception as exc:
            runs.append({"niche": niche, "error": f"{type(exc).__name__}: {exc}"})

    return {
        "status": "ok",
        "trigger": "cron",
        "niches": DEFAULT_DAILY_NICHES,
        "currency": DEFAULT_DAILY_CURRENCY,
        "warning": _currency_warning(DEFAULT_DAILY_CURRENCY),
        "runs": runs,
    }


@router.get("/site", response_class=HTMLResponse)
def site():
    html = _last_pipeline.get("site_html")
    if not html:
        return HTMLResponse(
            "<h1>Nenhum site gerado ainda.</h1><p>Rode POST /api/v1/real-mining/pipeline primeiro.</p>",
            status_code=404,
        )
    return HTMLResponse(html)


@router.get("/site/preview", response_class=HTMLResponse)
def site_preview(
    product_name: str = Query("Produto Campeao"),
    currency: str = Query("BRL"),
    search_terms: str = Query(""),
):
    """Gera um site de demonstracao sem precisar de token (valida o gerador).

    Este endpoint FUNCIONA HOJE, mesmo com a Ad Library bloqueada — e a
    metade do produto que nao depende de aprovacao da Meta.
    """
    products = ad_library_real.generate_products(
        product_name, currency.upper(), ad_body=search_terms
    )
    main_ad = ad_library_real.remodel_ad({"page_name": "preview"}, product_name)
    return HTMLResponse(ad_library_real.build_site_html(product_name, products, main_ad))
