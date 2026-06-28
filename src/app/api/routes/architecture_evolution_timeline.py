"""Missao 123 - Architecture Evolution Timeline.

Mesma convencao de endpoint das Missoes 53/55/56/57/58/59/60/122:
"live" (JSON, calculado agora) e "markdown" (texto legivel por
humano) - ambos via `Depends(get_architecture_evolution_timeline_service)`,
nunca uma chamada hardcoded direto na rota.

Adicionado a `app/api/routes/` sem nenhuma edicao em `safe_router.py` -
`discover_route_modules()` (Missao 54) encontra este modulo automaticamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_architecture_evolution_timeline_service
from app.services.architecture_evolution_timeline_service import (
    ArchitectureEvolutionTimelineService,
)

router = APIRouter(prefix="/architecture-evolution", tags=["Evolucao da Arquitetura"])


@router.get("/live")
def architecture_evolution_live(
    service: ArchitectureEvolutionTimelineService = Depends(
        get_architecture_evolution_timeline_service
    ),
) -> dict:
    return service.evolution_report()


@router.get("/markdown", response_class=PlainTextResponse)
def architecture_evolution_markdown(
    service: ArchitectureEvolutionTimelineService = Depends(
        get_architecture_evolution_timeline_service
    ),
) -> PlainTextResponse:
    markdown = service.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
