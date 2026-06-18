from fastapi import APIRouter

from app.schemas.content_orchestrator import ContentOrchestratorRequest, ContentOrchestratorResponse
from app.services.content_orchestrator import ContentOrchestrator

router = APIRouter(prefix="/content-orchestrator", tags=["Content Orchestrator"])


@router.post("/route", response_model=ContentOrchestratorResponse)
def route_content(payload: ContentOrchestratorRequest):
    return ContentOrchestrator().route(payload)
