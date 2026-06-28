from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.operational_intelligence import OperationalIntelligenceResponse
from app.services.operational_intelligence_service import OperationalIntelligenceService

router = APIRouter(
    prefix="/operational-intelligence",
    tags=["Operational Intelligence Hub"],
)


@router.get("/health-panel/live", response_model=OperationalIntelligenceResponse)
def operational_intelligence_health_panel_live(db: Session = Depends(get_db)):
    return OperationalIntelligenceService(db).health_panel()


@router.get("/health-panel/markdown", response_class=PlainTextResponse)
def operational_intelligence_health_panel_markdown(db: Session = Depends(get_db)):
    markdown = OperationalIntelligenceService(db).render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
