"""Missao 56 - AI Code Reviewer.

Mesma convencao de endpoint das Missoes 53/55 (certification.py,
architecture_audit.py): "live" (JSON, calculado agora) + "markdown" (texto
legivel por humano), ambos via `Depends(get_code_review_service)` - nunca
uma chamada hardcoded direto na rota.

Este arquivo tambem e mais uma demonstracao viva da Missao 54: foi
adicionado a `app/api/routes/` sem nenhuma edicao em `safe_router.py` -
`discover_route_modules()` encontra este modulo automaticamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_code_review_service
from app.services.code_review_service import CodeReviewService

router = APIRouter(prefix="/code-review", tags=["Revisao Automatica de Codigo"])


@router.get("/live")
def code_review_live(
    review: CodeReviewService = Depends(get_code_review_service),
) -> dict:
    return review.review_repository()


@router.get("/markdown", response_class=PlainTextResponse)
def code_review_markdown(
    review: CodeReviewService = Depends(get_code_review_service),
) -> PlainTextResponse:
    markdown = review.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
