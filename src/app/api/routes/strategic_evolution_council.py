"""Missao 130 - rotas do Conselho Estrategico de Evolucao.

Rota fina sobre `StrategicEvolutionCouncilService` - ver docstring do
servico para as seis fontes reais por tras do parecer multidisciplinar
e para a heuristica explicita de `recommendation`. Descoberta
automatica via `discover_route_modules()` (Missao 54) - nenhuma edicao
em `safe_router.py`.

`change_description` e opcional e so um rotulo de registro (nao
analisado) - ver docstring do servico."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_strategic_evolution_council_service
from app.services.strategic_evolution_council_service import (
    StrategicEvolutionCouncilService,
)

router = APIRouter(prefix="/evolution-council", tags=["Conselho de Evolucao"])


@router.get("/live")
def live(
    change_description: str | None = None,
    service: StrategicEvolutionCouncilService = Depends(get_strategic_evolution_council_service),
) -> dict:
    return service.council_review(change_description=change_description)


@router.get("/markdown", response_class=PlainTextResponse)
def markdown(
    change_description: str | None = None,
    service: StrategicEvolutionCouncilService = Depends(get_strategic_evolution_council_service),
) -> str:
    report = service.council_review(change_description=change_description)
    return service.render_markdown(report)
