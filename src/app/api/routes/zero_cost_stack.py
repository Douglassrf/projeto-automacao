from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.zero_cost_stack import ZeroCostStackRequest, ZeroCostStackResponse
from app.services.zero_cost_stack import ZeroCostStackPlanner

router = APIRouter(prefix="/zero-cost-stack", tags=["Zero-Cost Hybrid Stack"])


@router.post("/blueprint", response_model=ZeroCostStackResponse)
def build_zero_cost_blueprint(payload: ZeroCostStackRequest, current_user: User = Depends(get_current_user)):
    try:
        return ZeroCostStackPlanner().build(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha ao gerar blueprint custo zero: {exc}") from exc
