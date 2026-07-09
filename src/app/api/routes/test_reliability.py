from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.test_reliability import TestReliabilityResponse
from app.services.test_reliability_service import get_test_reliability_service

router = APIRouter(prefix="/test-reliability", tags=["Test Reliability Program"])


@router.get("/live", response_model=TestReliabilityResponse)
def test_reliability_live():
    return get_test_reliability_service().reliability_report()


@router.get("/markdown", response_class=PlainTextResponse)
def test_reliability_markdown():
    return PlainTextResponse(content=get_test_reliability_service().render_markdown(), media_type="text/markdown")
