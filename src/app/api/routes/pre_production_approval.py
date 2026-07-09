from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.pre_production_approval import PreProductionApprovalResponse
from app.services.pre_production_approval_service import PreProductionApprovalService, get_pre_production_approval_service

router = APIRouter(prefix="/pre-production-approval", tags=["Pre Production Approval"])


@router.get("/live", response_model=PreProductionApprovalResponse)
def pre_production_approval_live(db: Session = Depends(get_db)):
    return get_pre_production_approval_service(db).approval_report()


@router.get("/markdown", response_class=PlainTextResponse)
def pre_production_approval_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(content=get_pre_production_approval_service(db).render_markdown(), media_type="text/markdown")
