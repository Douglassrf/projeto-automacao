from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.predictive_health import PredictiveHealthResponse
from app.services.predictive_health_service import PredictiveHealthService

router = APIRouter(
    prefix="/predictive-health",
    tags=["Predictive Health Monitor"],
)


@router.get("/monitor/live", response_model=PredictiveHealthResponse)
def predictive_health_monitor_live(db: Session = Depends(get_db)):
    return PredictiveHealthService(db).monitor_report()


@router.get("/monitor/markdown", response_class=PlainTextResponse)
def predictive_health_monitor_markdown(db: Session = Depends(get_db)):
    markdown = PredictiveHealthService(db).render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
