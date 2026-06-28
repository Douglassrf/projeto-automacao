"""Missao 58 - Automatic Technical Debt Manager.

Mesma convencao de endpoint das Missoes 53/55/56/57 (certification.py,
architecture_audit.py, code_review.py, evolution_dashboard.py): "live"
(JSON, calculado agora) + "markdown" (texto legivel por humano), ambos via
`Depends(get_tech_debt_manager_service)` - nunca uma chamada hardcoded
direto na rota.

Este arquivo tambem e mais uma demonstracao viva da Missao 54: foi
adicionado a `app/api/routes/` sem nenhuma edicao em `safe_router.py` -
`discover_route_modules()` encontra este modulo automaticamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_tech_debt_manager_service
from app.services.tech_debt_manager_service import TechDebtManagerService

router = APIRouter(prefix="/tech-debt", tags=["Gestor Automatico de Divida Tecnica"])


@router.get("/live")
def tech_debt_live(
    manager: TechDebtManagerService = Depends(get_tech_debt_manager_service),
) -> dict:
    return manager.debt_report()


@router.get("/markdown", response_class=PlainTextResponse)
def tech_debt_markdown(
    manager: TechDebtManagerService = Depends(get_tech_debt_manager_service),
) -> PlainTextResponse:
    markdown = manager.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
