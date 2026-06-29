from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.ffmpeg_production import FfmpegProductionResponse
from app.services.ffmpeg_production_service import get_ffmpeg_production_service

router = APIRouter(prefix="/ffmpeg-production", tags=["FFmpeg Production Layer"])


@router.get("/live", response_model=FfmpegProductionResponse)
def ffmpeg_production_live():
    return get_ffmpeg_production_service().production_report()


@router.get("/markdown", response_class=PlainTextResponse)
def ffmpeg_production_markdown():
    return PlainTextResponse(
        content=get_ffmpeg_production_service().render_markdown(),
        media_type="text/markdown",
    )
