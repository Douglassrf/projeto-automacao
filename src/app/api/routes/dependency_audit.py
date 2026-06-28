from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.dependency_audit import DependencyAuditResponse
from app.services.dependency_audit_service import DependencyAuditService

router = APIRouter(prefix="/dependency-audit", tags=["Auditoria de Dependencias"])


@router.get("/live", response_model=DependencyAuditResponse)
def dependency_audit_live():
    return DependencyAuditService().audit()


@router.get("/markdown", response_class=PlainTextResponse)
def dependency_audit_markdown():
    markdown = DependencyAuditService().render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
