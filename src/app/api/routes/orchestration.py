from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.orchestration import OrchestrationRequest, OrchestrationResponse
from app.services.orchestration_pipeline import FreeStackOrchestrator

router = APIRouter(prefix="/orchestration", tags=["Free Stack Orchestration"])


@router.post("/run", response_model=OrchestrationResponse)
def run_orchestration(payload: OrchestrationRequest, current_user: User = Depends(get_current_user)):
    try:
        return FreeStackOrchestrator().run(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha na orquestração: {exc}") from exc


@router.post("/webhook-preview")
def webhook_preview(payload: dict, current_user: User = Depends(get_current_user)):
    return {
        "status": "received",
        "message": "Payload recebido. Use este endpoint para testar Bash/n8n antes de conectar webhooks externos.",
        "keys": sorted(payload.keys()),
    }
