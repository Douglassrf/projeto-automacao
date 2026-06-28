from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.autonomous_operations import AutonomousOperationsResponse
from app.services.autonomous_operations_service import AutonomousOperationsService

router = APIRouter(
    prefix="/autonomous-operations",
    tags=["Autonomous Operations Readiness"],
)


@router.get("/readiness/live", response_model=AutonomousOperationsResponse)
def autonomous_operations_readiness_live(db: Session = Depends(get_db)):
    return AutonomousOperationsService(db).readiness_report()


@router.get("/readiness/markdown", response_class=PlainTextResponse)
def autonomous_operations_readiness_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(
        content=AutonomousOperationsService(db).render_markdown(),
        media_type="text/markdown",
    )
