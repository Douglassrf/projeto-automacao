"""Missao 127 - Continuous Architecture Scoring.

Rota fina sobre `ContinuousArchitectureScoringService` - ver docstring do
servico para as cinco fontes reais por tras de cada eixo. Descoberta
automatica via `discover_route_modules()` (Missao 54) - nenhuma edicao em
`safe_router.py`."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_architecture_scoring_service
from app.services.architecture_scoring_service import ContinuousArchitectureScoringService

router = APIRouter(prefix="/architecture-scoring", tags=["Pontuacao de Arquitetura"])


@router.get("/live")
def live(
    service: ContinuousArchitectureScoringService = Depends(get_architecture_scoring_service),
) -> dict:
    return service.score_report()


@router.get("/markdown", response_class=PlainTextResponse)
def markdown(
    service: ContinuousArchitectureScoringService = Depends(get_architecture_scoring_service),
) -> str:
    return service.render_markdown()
