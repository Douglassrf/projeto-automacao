"""Missao 60 - Enterprise Readiness Certification.

Mesma convencao de endpoint das Missoes 53/55/56/57/58/59
(certification.py, architecture_audit.py, code_review.py,
evolution_dashboard.py, tech_debt.py, architecture_stress_test.py):
"live" (JSON, calculado agora) + "markdown" (texto legivel por humano),
ambos via `Depends(get_enterprise_readiness_service)` - nunca uma chamada
hardcoded direto na rota.

Este arquivo tambem e mais uma demonstracao viva da Missao 54: foi
adicionado a `app/api/routes/` sem nenhuma edicao em `safe_router.py` -
`discover_route_modules()` encontra este modulo automaticamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_enterprise_readiness_service
from app.services.enterprise_readiness_service import EnterpriseReadinessService

router = APIRouter(
    prefix="/enterprise-readiness", tags=["Certificacao de Prontidao Enterprise"]
)


@router.get("/live")
def enterprise_readiness_live(
    service: EnterpriseReadinessService = Depends(get_enterprise_readiness_service),
) -> dict:
    return service.readiness_report()


@router.get("/markdown", response_class=PlainTextResponse)
def enterprise_readiness_markdown(
    service: EnterpriseReadinessService = Depends(get_enterprise_readiness_service),
) -> PlainTextResponse:
    markdown = service.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
