from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.video_pipeline import VideoRenderRequest, VideoRenderResponse
from app.services.video_pipeline import VideoRenderPipeline
from app.core.route_security import ai_heavy_security_guard

router = APIRouter(prefix="/video", tags=["Video Render Pipeline"])


@router.post("/render", response_model=VideoRenderResponse)
def render_video(payload: VideoRenderRequest, current_user: User = Depends(get_current_user)):
    try:
        ai_heavy_security_guard(payload.model_dump(mode="json"))
        return VideoRenderPipeline().render(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha ao renderizar vídeo: {exc}") from exc
