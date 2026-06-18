from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.serverless_render import ServerlessRenderRequest, ServerlessRenderJobResponse
from app.services.serverless_render import ServerlessRenderPlanner

router = APIRouter(prefix="/serverless-render", tags=["Serverless Render"])


@router.post("/job", response_model=ServerlessRenderJobResponse)
def create_serverless_render_job(payload: ServerlessRenderRequest, current_user: User = Depends(get_current_user)):
    try:
        return ServerlessRenderPlanner().create_job(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha ao criar job serverless: {exc}") from exc
