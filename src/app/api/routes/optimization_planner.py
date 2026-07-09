"""Missao 128 - rotas do Autonomous Optimization Planner.

Descoberta automatica via `discover_route_modules()` (Missao 54) - nao
precisa editar `safe_router.py`."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_optimization_planner_service
from app.services.optimization_planner_service import AutonomousOptimizationPlannerService

router = APIRouter(prefix="/optimization-planner", tags=["Planejador de Otimizacao"])


@router.get("/live")
def live(
    service: AutonomousOptimizationPlannerService = Depends(get_optimization_planner_service),
) -> dict:
    return service.optimization_plan()


@router.get("/markdown", response_class=PlainTextResponse)
def markdown(
    service: AutonomousOptimizationPlannerService = Depends(get_optimization_planner_service),
) -> str:
    return service.render_markdown()
