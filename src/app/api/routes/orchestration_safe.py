from fastapi import APIRouter

from app.schemas.orchestration import OrchestrationRequest, OrchestrationResponse
from app.services.orchestration_pipeline_safe import OrchestrationPipelineSafe


router = APIRouter(prefix="/orchestration-safe", tags=["Orchestration Safe"])


@router.get("/health")
def health():
    return OrchestrationPipelineSafe().health()


@router.get("/mock-run", response_model=OrchestrationResponse)
def mock_run():
    return OrchestrationPipelineSafe().run_mock_cycle()


@router.post("/run", response_model=OrchestrationResponse)
def run(payload: OrchestrationRequest):
    return OrchestrationPipelineSafe().run(payload)
