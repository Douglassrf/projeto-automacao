"""Missao 126 - Intelligent Release Governance.

Rota fina sobre `IntelligentReleaseGovernanceService` - ver docstring do
servico para as cinco fontes reais por tras do veredito `release_approved`.
Descoberta automatica via `discover_route_modules()` (Missao 54) - nenhuma
edicao em `safe_router.py`."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_intelligent_release_governance_service
from app.services.intelligent_release_governance_service import (
    IntelligentReleaseGovernanceService,
)

router = APIRouter(prefix="/release-governance", tags=["Governanca de Release"])


@router.get("/live")
def live(
    service: IntelligentReleaseGovernanceService = Depends(get_intelligent_release_governance_service),
) -> dict:
    return service.validate_release()


@router.get("/markdown", response_class=PlainTextResponse)
def markdown(
    service: IntelligentReleaseGovernanceService = Depends(get_intelligent_release_governance_service),
) -> str:
    return service.render_markdown()
