"""Missao 131 - rotas da Enterprise Excellence Certification (capstone
da Fase v2.1).

Rota fina sobre `EnterpriseExcellenceCertificationService` - ver
docstring do servico para o mapeamento das 12 dimensoes para os
motores reais reusados (Missoes 42/47/48/49/56/57/58/122/123/124/127)
e para o consumo direto do parecer da Missao 130. Descoberta automatica
via `discover_route_modules()` (Missao 54) - nenhuma edicao em
`safe_router.py`.

Nota de custo: este relatorio chama, entre outras coisas,
`EnterpriseQualityObservatoryService.quality_report()` (M124), que por
sua vez chama o teste de carga real da Missao 59 - custo tipico de
~40s neste ambiente de dev (ver docstring do servico)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_enterprise_excellence_certification_service
from app.services.enterprise_excellence_certification_service import (
    EnterpriseExcellenceCertificationService,
)

router = APIRouter(prefix="/enterprise-excellence", tags=["Enterprise Excellence Certification"])


@router.get("/live")
def live(
    service: EnterpriseExcellenceCertificationService = Depends(
        get_enterprise_excellence_certification_service
    ),
) -> dict:
    return service.certification_report()


@router.get("/markdown", response_class=PlainTextResponse)
def markdown(
    service: EnterpriseExcellenceCertificationService = Depends(
        get_enterprise_excellence_certification_service
    ),
) -> str:
    report = service.certification_report()
    return service.render_markdown(report)
