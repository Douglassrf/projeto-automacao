"""Rotas do modo REAL: mineracao na Ad Library + pipeline completo."""

from __future__ import annotations

import os

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.services import ad_library_real

router = APIRouter(prefix="/real-mining", tags=["Real Mining - Ad Library"])

_last_pipeline: dict = {}

# Nichos/produtos que o cron diario garimpa automaticamente na Ad Library,
# buscando os anuncios campeao (mais recorrentes e ainda ativos) para
# remodelagem. Ajuste esta lista conforme os produtos ativos do momento.
DEFAULT_DAILY_NICHES: list[str] = ["Renda em Dolar"]


class MiningRequest(BaseModel):
    search_terms: str = Field(..., min_length=2, description="Termo do produto/nicho")
    currency: str = Field("BRL", description="EUR, USD ou BRL")
    min_active_ads: int = Field(15, ge=1, le=100)
    limit: int = Field(200, ge=10, le=300)


class PipelineRequest(MiningRequest):
    product_name: str | None = None


@router.get("/status")
def status():
    token_ok = ad_library_real._get_token() is not None
    return {
        "status": "ok",
        "mode": "real",
        "token_configured": token_ok,
        "deepseek_configured": ad_library_real._deepseek_key() is not None,
        "copywriter": "deepseek" if ad_library_real._deepseek_key() else "template",
        "message": (
            "Pronto para minerar a Ad Library em modo real."
            if token_ok
            else "Falta configurar META_AD_LIBRARY_TOKEN nas variaveis da Vercel."
        ),
        "currencies": list(ad_library_real.CURRENCY_COUNTRIES.keys()),
        "classification": {"BRONZE": "15+", "PRATA": "20+", "OURO": "25+"},
        "daily_cron": {
            "enabled": True,
            "niches": DEFAULT_DAILY_NICHES,
            "schedule": "todo dia as 09:00 (America/Sao_Paulo)",
        },
    }


@router.post("/search")
def search(payload: MiningRequest):
    return ad_library_real.search_ad_library(
        payload.search_terms,
        currency=payload.currency,
        min_active_ads=payload.min_active_ads,
        limit=payload.limit,
    )


@router.post("/pipeline")
def pipeline(payload: PipelineRequest):
    global _last_pipeline
    result = ad_library_real.run_full_pipeline(
        payload.search_terms,
        currency=payload.currency,
        min_active_ads=payload.min_active_ads,
        product_name=payload.product_name,
    )
    if result.get("status") == "ok" and result.get("site_html"):
        _last_pipeline = result
        # nao poluir o JSON com o HTML inteiro
        result = {**result, "site_html": "gerado - abra GET /api/v1/real-mining/site"}
    return result


@router.get("/cron-daily")
def cron_daily(request: Request):
    """Disparo automatico diario da mineracao de anuncios campeao.

    Garimpa, para cada nicho em DEFAULT_DAILY_NICHES, os 15+ anuncios com
    mais recorrencia/ativos na Ad Library e roda o pipeline completo de
    remodelagem (mesma logica de POST /pipeline), sem precisar de acao manual.

    Chamada automaticamente pelo Vercel Cron (ver vercel.json). Protegida por
    CRON_SECRET quando essa variavel estiver configurada nas env vars da
    Vercel - a Vercel envia 'Authorization: Bearer <CRON_SECRET>' sozinha.
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
                currency="BRL",
                min_active_ads=15,
                product_name=niche,
            )
            if result.get("status") == "ok" and result.get("site_html"):
                _last_pipeline = result
                result = {**result, "site_html": "gerado - abra GET /api/v1/real-mining/site"}
            runs.append({"niche": niche, "result": result})
        except Exception as exc:  # nao deixar 1 nicho com erro derrubar os demais
            runs.append({"niche": niche, "error": f"{type(exc).__name__}: {exc}"})

    return {"status": "ok", "trigger": "cron", "niches": DEFAULT_DAILY_NICHES, "runs": runs}


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
def site_preview(product_name: str = Query("Produto Campeao"), currency: str = Query("BRL")):
    """Gera um site de demonstracao sem precisar de token (para validar o gerador)."""
    products = ad_library_real.generate_products(product_name, currency.upper())
    main_ad = ad_library_real.remodel_ad({"page_name": "preview"}, product_name)
    return HTMLResponse(ad_library_real.build_site_html(product_name, products, main_ad))
