from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.hybrid_stack import HybridStackRequest, HybridStackResponse
from app.services.hybrid_stack import HybridNoGpuStackPlanner

router = APIRouter(prefix="/hybrid-stack", tags=["Hybrid No-GPU Stack"])


@router.post("/plan", response_model=HybridStackResponse)
def build_hybrid_stack_plan(payload: HybridStackRequest, current_user: User = Depends(get_current_user)):
    try:
        return HybridNoGpuStackPlanner().build_plan(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha ao gerar plano híbrido: {exc}") from exc
