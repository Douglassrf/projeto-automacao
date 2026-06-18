from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.learning_loop import CapiIngestRequest, CapiIngestResponse, LearningLoopRequest, LearningLoopResponse
from app.services.learning_loop import CapiLearningLoopService

router = APIRouter(prefix="/learning-loop", tags=["CAPI Learning Loop"])


@router.post("/capi/ingest", response_model=CapiIngestResponse)
def ingest_capi_events(payload: CapiIngestRequest, current_user: User = Depends(get_current_user)):
    try:
        return CapiLearningLoopService().ingest_capi_events(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha ao registrar evento CAPI: {exc}") from exc


@router.post("/generate-variations", response_model=LearningLoopResponse)
def generate_learning_variations(payload: LearningLoopRequest, current_user: User = Depends(get_current_user)):
    try:
        return CapiLearningLoopService().run_learning_loop(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha no loop de aprendizado: {exc}") from exc


@router.post("/real-controlled")
def run_learning_loop_real_controlled(payload: dict, current_user: User = Depends(get_current_user)):
    try:
        events_payload = CapiIngestRequest(**payload.get("events_payload", {}))
        loop_payload = LearningLoopRequest(**payload.get("loop_payload", {}))
        return CapiLearningLoopService().run_real_controlled_loop(events_payload, loop_payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha no learning loop real controlado: {exc}") from exc
