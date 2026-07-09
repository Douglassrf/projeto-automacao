from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.resource_optimization import ResourceOptimizationResponse
from app.services.resource_optimization_service import ResourceOptimizationService

router = APIRouter(prefix="/resource-optimization", tags=["Resource Optimization Engine"])


@router.get("/engine/live", response_model=ResourceOptimizationResponse)
def resource_optimization_engine_live(db: Session = Depends(get_db)):
    return ResourceOptimizationService(db).optimization_report()


@router.get("/engine/markdown", response_class=PlainTextResponse)
def resource_optimization_engine_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(
        content=ResourceOptimizationService(db).render_markdown(),
        media_type="text/markdown",
    )
