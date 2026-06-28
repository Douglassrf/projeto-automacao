"""Missao 125 - Predictive Maintenance Center.

Mesma convencao de endpoint das Missoes 53/55/56/57/58/59/60/122/123/124:
"live" (JSON, calculado agora) e "markdown" (texto legivel por
humano) - ambos via `Depends(get_predictive_maintenance_service)`,
nunca uma chamada hardcoded direto na rota.

Adicionado a `app/api/routes/` sem nenhuma edicao em `safe_router.py` -
`discover_route_modules()` (Missao 54) encontra este modulo automaticamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_predictive_maintenance_service
from app.services.predictive_maintenance_service import PredictiveMaintenanceService

router = APIRouter(prefix="/predictive-maintenance", tags=["Manutencao Preditiva"])


@router.get("/live")
def predictive_maintenance_live(
    service: PredictiveMaintenanceService = Depends(get_predictive_maintenance_service),
) -> dict:
    return service.maintenance_report()


@router.get("/markdown", response_class=PlainTextResponse)
def predictive_maintenance_markdown(
    service: PredictiveMaintenanceService = Depends(get_predictive_maintenance_service),
) -> PlainTextResponse:
    markdown = service.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
