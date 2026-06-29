from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.platform_intelligence import PlatformIntelligenceResponse
from app.services.platform_intelligence_service import PlatformIntelligenceService

router = APIRouter(prefix="/platform-intelligence", tags=["Platform Intelligence v1.9"])


@router.get("/snapshot", response_model=PlatformIntelligenceResponse)
def platform_intelligence_snapshot(db: Session = Depends(get_db)):
    return PlatformIntelligenceService(db).platform_snapshot()


@router.get("/report/markdown", response_class=PlainTextResponse)
def platform_intelligence_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(
        content=PlatformIntelligenceService(db).render_markdown(),
        media_type="text/markdown",
    )
