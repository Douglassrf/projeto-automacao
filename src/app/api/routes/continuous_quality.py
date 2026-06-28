from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.continuous_quality import ContinuousQualityResponse
from app.services.continuous_quality_service import ContinuousQualityService

router = APIRouter(prefix="/quality-gate", tags=["Continuous Quality Gate"])


@router.get("/report/live", response_model=ContinuousQualityResponse)
def quality_gate_report_live(db: Session = Depends(get_db)):
    return ContinuousQualityService(db).quality_report()


@router.get("/report/markdown", response_class=PlainTextResponse)
def quality_gate_report_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(
        content=ContinuousQualityService(db).render_markdown(),
        media_type="text/markdown",
    )
