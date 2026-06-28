"""Missao 122 - Engineering Memory Core.

Mesma convencao de endpoint das Missoes 53/55/56/57/58/59/60: "live"
(JSON, calculado agora), "markdown" (texto legivel por humano) e, unico
desta missao, "/trace" (busca textual, criterio de aceite "qualquer
decisao do projeto pode ser rastreada") - todos via
`Depends(get_engineering_memory_core_service)`, nunca uma chamada
hardcoded direto na rota.

Adicionado a `app/api/routes/` sem nenhuma edicao em `safe_router.py` -
`discover_route_modules()` (Missao 54) encontra este modulo automaticamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.core.container import get_engineering_memory_core_service
from app.services.engineering_memory_core_service import EngineeringMemoryCoreService

router = APIRouter(prefix="/engineering-memory", tags=["Memoria de Engenharia"])


@router.get("/live")
def engineering_memory_live(
    service: EngineeringMemoryCoreService = Depends(get_engineering_memory_core_service),
) -> dict:
    return service.memory_report()


@router.get("/markdown", response_class=PlainTextResponse)
def engineering_memory_markdown(
    service: EngineeringMemoryCoreService = Depends(get_engineering_memory_core_service),
) -> PlainTextResponse:
    markdown = service.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")


@router.get("/trace")
def engineering_memory_trace(
    query: str = Query(..., min_length=1),
    service: EngineeringMemoryCoreService = Depends(get_engineering_memory_core_service),
) -> dict:
    return service.trace(query)
