from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.data_integrity import DataIntegrityResponse
from app.services.data_integrity_service import DataIntegrityService

router = APIRouter(prefix="/data-integrity", tags=["Data Integrity Framework"])


@router.get("/check/live", response_model=DataIntegrityResponse)
def data_integrity_check_live(db: Session = Depends(get_db)):
    return DataIntegrityService(db).integrity_report()


@router.get("/check/markdown", response_class=PlainTextResponse)
def data_integrity_check_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(
        content=DataIntegrityService(db).render_markdown(),
        media_type="text/markdown",
    )
