from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.performance_certification import PerformanceCertificationResponse
from app.services.performance_certification_service import get_performance_certification_service

router = APIRouter(prefix="/performance-certification", tags=["Performance Certification"])


@router.get("/live", response_model=PerformanceCertificationResponse)
def performance_certification_live():
    return get_performance_certification_service().performance_report()


@router.get("/markdown", response_class=PlainTextResponse)
def performance_certification_markdown():
    return PlainTextResponse(content=get_performance_certification_service().render_markdown(), media_type="text/markdown")
