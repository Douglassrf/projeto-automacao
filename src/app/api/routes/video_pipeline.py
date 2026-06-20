from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.route_security import ai_heavy_security_guard
from app.domain.models import User
from app.schemas.video_pipeline import VideoRenderRequest, VideoRenderResponse
from app.services.observability import immutable_audit_event
from app.services.video_pipeline import VideoRenderPipeline

router = APIRouter(prefix="/video", tags=["Video Render Pipeline"])


@router.post("/render", response_model=VideoRenderResponse)
def render_video(payload: VideoRenderRequest, current_user: User = Depends(get_current_user)):
    guard = ai_heavy_security_guard(payload.model_dump(mode="json"))
    actor_label = getattr(current_user, "email", None) or getattr(current_user, "name", "unknown")

    if guard["status"] == "blocked":
        immutable_audit_event(
            actor=str(actor_label),
            action="video_pipeline.render.blocked",
            resource_type="video_pipeline",
            resource_id=payload.product_name,
            status="blocked",
            details={
                "blocked_reasons": guard["blocked_reasons"],
                "requires_human_approval": guard["requires_human_approval"],
                "scene_provider": payload.scene_provider,
                "voice_provider": payload.voice_provider,
            },
        )
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Renderização de vídeo bloqueada pelo guard de segurança de IA pesada.",
                "blocked_reasons": guard["blocked_reasons"],
                "requires_human_approval": guard["requires_human_approval"],
            },
        )

    try:
        return VideoRenderPipeline().render(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha ao renderizar vídeo: {exc}") from exc
