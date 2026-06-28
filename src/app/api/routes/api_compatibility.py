from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api_compatibility import ApiCompatibilityResponse
from app.services.api_compatibility_service import ApiCompatibilityService

router = APIRouter(prefix="/api-compatibility", tags=["API Compatibility Center"])


@router.get("/center/live", response_model=ApiCompatibilityResponse)
def api_compatibility_center_live(db: Session = Depends(get_db)):
    return ApiCompatibilityService(db).compatibility_report()


@router.get("/center/markdown", response_class=PlainTextResponse)
def api_compatibility_center_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(
        content=ApiCompatibilityService(db).render_markdown(),
        media_type="text/markdown",
    )
