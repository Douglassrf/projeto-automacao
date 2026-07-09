from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.ci_stabilization import CiStabilizationResponse
from app.services.ci_stabilization_service import get_ci_stabilization_service

router = APIRouter(
    prefix="/ci-stabilization",
    tags=["CI/CD Stabilization"],
)


@router.get("/live", response_model=CiStabilizationResponse)
def ci_stabilization_live():
    return get_ci_stabilization_service().stabilization_report()


@router.get("/markdown", response_class=PlainTextResponse)
def ci_stabilization_markdown():
    return PlainTextResponse(
        content=get_ci_stabilization_service().render_markdown(),
        media_type="text/markdown",
    )
