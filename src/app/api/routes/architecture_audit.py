"""Missao 55 - Continuous Architecture Audit.

Mesma convencao de endpoint da Missao 53 (app/api/routes/certification.py):
endpoint "live" (JSON, calculado agora) + endpoint "markdown" (texto
legivel por humano), ambos via `Depends(get_architecture_audit_service)` -
nunca uma chamada hardcoded direto na rota.

Este arquivo tambem serve de demonstracao viva da Missao 54: foi
adicionado a `app/api/routes/` sem nenhuma edicao em `safe_router.py` -
`discover_route_modules()` encontra este modulo automaticamente.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.container import get_architecture_audit_service
from app.services.architecture_audit_service import ArchitectureAuditService

router = APIRouter(prefix="/architecture-audit", tags=["Auditoria Continua de Arquitetura"])


@router.get("/live")
def architecture_audit_live(
    audit: ArchitectureAuditService = Depends(get_architecture_audit_service),
) -> dict:
    return audit.audit()


@router.get("/markdown", response_class=PlainTextResponse)
def architecture_audit_markdown(
    audit: ArchitectureAuditService = Depends(get_architecture_audit_service),
) -> PlainTextResponse:
    markdown = audit.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
