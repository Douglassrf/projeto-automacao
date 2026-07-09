from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.engineering_control_tower_service import EngineeringControlTowerService

router = APIRouter(prefix="/engineering-control-tower", tags=["Engineering Control Tower"])


@router.get("/live")
def engineering_control_tower_live(db: Session = Depends(get_db)) -> dict:
    return EngineeringControlTowerService(db).snapshot()


@router.get("/markdown", response_class=PlainTextResponse)
def engineering_control_tower_markdown(db: Session = Depends(get_db)) -> PlainTextResponse:
    return PlainTextResponse(
        content=EngineeringControlTowerService(db).render_markdown(),
        media_type="text/markdown",
    )
