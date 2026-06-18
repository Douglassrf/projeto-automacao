from fastapi import APIRouter

from app.schemas.video_pipeline import VideoRenderRequest
from app.services.video_pipeline_bridge import VideoPipelineBridge


router = APIRouter(prefix="/video-pipeline-safe", tags=["Video Pipeline Safe"])


@router.get("/health")
def health():
    return VideoPipelineBridge().health()


@router.get("/mock-run")
def mock_run():
    return VideoPipelineBridge().run_mock_cycle()


@router.post("/render")
def render(payload: VideoRenderRequest):
    return VideoPipelineBridge().safe_render(payload=payload, product_name=payload.product_name, niche="")
