from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.recovery import RecoveryReportResponse, RecoverySweepResponse
from app.services.recovery_service import RecoveryService

router = APIRouter(prefix="/recovery", tags=["Testes de Recuperacao"])


@router.get("/report", response_model=RecoveryReportResponse)
def recovery_report(db: Session = Depends(get_db)):
    return RecoveryService(db).recovery_report()


@router.post("/sweep", response_model=RecoverySweepResponse)
def recovery_sweep(limit: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)):
    return RecoveryService(db).recover_stale_running_jobs(limit=limit)
