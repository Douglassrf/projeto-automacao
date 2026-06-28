from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.disaster_recovery_validation import DisasterRecoveryValidationResponse
from app.services.disaster_recovery_validation_service import DisasterRecoveryValidationService, get_disaster_recovery_validation_service

router = APIRouter(prefix="/disaster-recovery", tags=["Disaster Recovery Validation"])


@router.get("/live", response_model=DisasterRecoveryValidationResponse)
def disaster_recovery_validation_live(db: Session = Depends(get_db)):
    return get_disaster_recovery_validation_service(db).validation_report()


@router.get("/markdown", response_class=PlainTextResponse)
def disaster_recovery_validation_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(content=get_disaster_recovery_validation_service(db).render_markdown(), media_type="text/markdown")
