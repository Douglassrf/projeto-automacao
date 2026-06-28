"""Missao 57 - Evolution Dashboard.

Mesma convencao de endpoint das Missoes 53/55/56: endpoint "live" (JSON,
calculado agora) + endpoint "markdown" (texto legivel por humano), ambos
via `Depends(get_evolution_dashboard_service)` - nunca uma chamada
hardcoded direto na rota.

Este arquivo tambem serve de demonstracao viva da Missao 54: foi
adicionado a `app/api/routes/` sem nenhuma edicao em `safe_router.py` -
`discover_route_modules()` encontra este modulo automaticamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_evolution_dashboard_service
from app.services.evolution_dashboard_service import EvolutionDashboardService

router = APIRouter(prefix="/evolution-dashboard", tags=["Evolution Dashboard"])


@router.get("/live")
def evolution_dashboard_live(
    dashboard: EvolutionDashboardService = Depends(get_evolution_dashboard_service),
) -> dict:
    return dashboard.evolution_report()


@router.get("/markdown", response_class=PlainTextResponse)
def evolution_dashboard_markdown(
    dashboard: EvolutionDashboardService = Depends(get_evolution_dashboard_service),
):
    markdown = dashboard.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
