"""Missao 129 - rotas do Engineering Digital Twin.

Descoberta automatica via `discover_route_modules()` (Missao 54) - nao
precisa editar `safe_router.py`."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_digital_twin_service
from app.services.digital_twin_service import EngineeringDigitalTwinService

router = APIRouter(prefix="/digital-twin", tags=["Gemeo Digital"])


@router.get("/live")
def live(
    service: EngineeringDigitalTwinService = Depends(get_digital_twin_service),
) -> dict:
    return service.digital_twin_report()


@router.get("/markdown", response_class=PlainTextResponse)
def markdown(
    service: EngineeringDigitalTwinService = Depends(get_digital_twin_service),
) -> str:
    return service.render_markdown()
