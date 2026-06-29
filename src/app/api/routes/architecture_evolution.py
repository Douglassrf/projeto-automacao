from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.architecture_evolution import ArchitectureEvolutionResponse
from app.services.architecture_evolution_service import ArchitectureEvolutionService

router = APIRouter(prefix="/architecture-evolution", tags=["Architecture Evolution Report"])


@router.get("/report/live", response_model=ArchitectureEvolutionResponse)
def architecture_evolution_report_live(db: Session = Depends(get_db)):
    return ArchitectureEvolutionService(db).evolution_report()


@router.get("/report/markdown", response_class=PlainTextResponse)
def architecture_evolution_report_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(
        content=ArchitectureEvolutionService(db).render_markdown(),
        media_type="text/markdown",
    )
