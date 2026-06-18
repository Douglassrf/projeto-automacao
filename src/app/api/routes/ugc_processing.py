from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.core.config import get_settings, safe_project_path
from app.domain.models import User
from app.schemas.ugc_processing import UGCProcessResponse
from app.services.ugc_processing import UGCEdgeProcessor, UGCProcessingError

router = APIRouter(prefix="/ugc", tags=["UGC Edge Processing"])


@router.post("/process", response_model=UGCProcessResponse, status_code=status.HTTP_201_CREATED)
async def process_ugc_asset(
    file: UploadFile = File(...),
    target_preset: str = Form("social_ad"),
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    content = await file.read()
    processor = UGCEdgeProcessor(
        output_dir=str(safe_project_path(settings.ugc_output_dir, "data/ugc")),
        max_size_bytes=settings.ugc_max_bytes,
        image_target_width=settings.ugc_image_target_width,
        video_target_width=settings.ugc_video_target_width,
        video_crf=settings.ugc_video_crf,
    )
    try:
        result = processor.process(file.filename or "ugc_upload", content, target_preset=target_preset)
    except UGCProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UGCProcessResponse(**result.__dict__)
