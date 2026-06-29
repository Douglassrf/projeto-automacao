from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.production_launch_authorization import ProductionLaunchAuthorizationResponse
from app.services.production_launch_authorization_service import ProductionLaunchAuthorizationService, get_production_launch_authorization_service

router = APIRouter(prefix="/production-launch", tags=["Production Launch Authorization"])


@router.get("/live", response_model=ProductionLaunchAuthorizationResponse)
def production_launch_authorization_live(db: Session = Depends(get_db)):
    return get_production_launch_authorization_service(db).authorization_report()


@router.get("/markdown", response_class=PlainTextResponse)
def production_launch_authorization_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(content=get_production_launch_authorization_service(db).render_markdown(), media_type="text/markdown")
