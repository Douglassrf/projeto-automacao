"""Missao 59 - Architecture Stress Test.

Mesma convencao de endpoint das Missoes 53/55/56/57/58: endpoint "live"
(JSON, calculado agora, dispara o burst de verdade a cada chamada) +
endpoint "markdown" (texto legivel por humano), ambos via
`Depends(get_architecture_stress_test_service)` - nunca uma chamada
hardcoded direto na rota.

Este arquivo tambem serve de demonstracao viva da Missao 54, de novo:
foi adicionado a `app/api/routes/` sem nenhuma edicao em
`safe_router.py` - `discover_route_modules()` encontra este modulo
automaticamente.

Nota de carga: `/live` por padrao dispara 4 requisicoes (concorrencia 2)
por endpoint x 5 endpoints + 4 chamadas ao container = ~24 requisicoes
in-process por chamada a esta rota (~14s medido, dominado pelo dashboard
de evolucao da Missao 57, que nunca usa cache). Aceitavel para uma rota
de diagnostico chamada ocasionalmente, nunca em alta frequencia - mesma
logica de custo da Missao 27A (`/observability/load-test/mission-27a`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_architecture_stress_test_service
from app.services.architecture_stress_test_service import ArchitectureStressTestService

router = APIRouter(prefix="/architecture-stress-test", tags=["Teste de Estresse de Arquitetura"])


@router.get("/live")
def architecture_stress_test_live(
    stress_test: ArchitectureStressTestService = Depends(get_architecture_stress_test_service),
) -> dict:
    return stress_test.stress_report()


@router.get("/markdown", response_class=PlainTextResponse)
def architecture_stress_test_markdown(
    stress_test: ArchitectureStressTestService = Depends(get_architecture_stress_test_service),
):
    markdown = stress_test.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
