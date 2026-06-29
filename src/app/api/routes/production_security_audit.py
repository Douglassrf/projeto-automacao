from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.production_security_audit import ProductionSecurityAuditResponse
from app.services.production_security_audit_service import get_production_security_audit_service

router = APIRouter(prefix="/production-security-audit", tags=["Production Security Audit"])


@router.get("/live", response_model=ProductionSecurityAuditResponse)
def production_security_audit_live():
    return get_production_security_audit_service().audit_report()


@router.get("/markdown", response_class=PlainTextResponse)
def production_security_audit_markdown():
    return PlainTextResponse(content=get_production_security_audit_service().render_markdown(), media_type="text/markdown")
