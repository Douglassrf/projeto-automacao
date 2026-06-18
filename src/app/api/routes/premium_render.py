from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.premium_render import PremiumRenderRequest, PremiumRenderResponse, WorkerBlueprintResponse
from app.services.premium_render import PremiumRenderPipeline, worker_blueprint
from app.core.route_security import ai_heavy_security_guard

router = APIRouter(prefix="/premium-render", tags=["Premium Render / Distributed Workers"])


@router.post("/run", response_model=PremiumRenderResponse)
def run_premium_render(payload: PremiumRenderRequest, current_user: User = Depends(get_current_user)):
    try:
        guard = ai_heavy_security_guard(payload.model_dump(mode="json"))
        if guard["blocked_reasons"]:
            payload.dry_run = True
        return PremiumRenderPipeline().render(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha no premium render: {exc}") from exc


@router.get("/workers/blueprint", response_model=WorkerBlueprintResponse)
def get_worker_blueprint(current_user: User = Depends(get_current_user)):
    return worker_blueprint()
