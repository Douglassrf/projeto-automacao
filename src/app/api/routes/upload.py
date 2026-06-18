from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from app.api.deps import get_current_user
from app.domain.models import User

from app.core.config import get_settings
from app.schemas.upload import UploadResponse
from app.services.upload_security import UploadSecurityError, store_upload

router = APIRouter(prefix="/upload", tags=["Secure Upload"])


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    settings = get_settings()
    content = await file.read()

    try:
        stored = store_upload(
            filename=file.filename or "upload",
            content=content,
            upload_dir=settings.upload_dir,
            max_size_bytes=settings.upload_max_bytes,
        )
    except UploadSecurityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return UploadResponse(
        status="stored",
        original_filename=stored.original_filename,
        safe_original_filename=stored.safe_original_filename,
        stored_filename=stored.stored_filename,
        size_bytes=stored.size_bytes,
        detected_mime=stored.detected_mime,
    )
