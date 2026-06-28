"""Missao 124 - Enterprise Quality Observatory.

Mesma convencao de endpoint das Missoes 53/55/56/57/58/59/60/122/123:
"live" (JSON, calculado agora) e "markdown" (texto legivel por
humano) - ambos via `Depends(get_enterprise_quality_observatory_service)`,
nunca uma chamada hardcoded direto na rota.

Adicionado a `app/api/routes/` sem nenhuma edicao em `safe_router.py` -
`discover_route_modules()` (Missao 54) encontra este modulo automaticamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_enterprise_quality_observatory_service
from app.services.enterprise_quality_observatory_service import (
    EnterpriseQualityObservatoryService,
)

router = APIRouter(prefix="/quality-observatory", tags=["Observatorio de Qualidade"])


@router.get("/live")
def quality_observatory_live(
    service: EnterpriseQualityObservatoryService = Depends(
        get_enterprise_quality_observatory_service
    ),
) -> dict:
    return service.quality_report()


@router.get("/markdown", response_class=PlainTextResponse)
def quality_observatory_markdown(
    service: EnterpriseQualityObservatoryService = Depends(
        get_enterprise_quality_observatory_service
    ),
) -> PlainTextResponse:
    markdown = service.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
