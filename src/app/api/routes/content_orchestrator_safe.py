from fastapi import APIRouter

from app.schemas.content_orchestrator import ContentOrchestratorRequest
from app.services.content_orchestrator_bridge import ContentOrchestratorBridge


router = APIRouter(prefix="/content-orchestrator-safe", tags=["Content Orchestrator Safe"])


@router.get("/health")
def health():
    return ContentOrchestratorBridge().health()


@router.get("/mock-run")
def mock_run():
    return ContentOrchestratorBridge().run_mock_cycle()


@router.post("/route")
def route(payload: ContentOrchestratorRequest):
    return ContentOrchestratorBridge().run_cycle(payload=payload, product_name=payload.title, niche="")
