from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.diagnostics import DiagnosticCheckResponse, DiagnosticsReportResponse
from app.services.diagnostics_service import DiagnosticsService, UnknownDiagnosticCheckError

router = APIRouter(prefix="/diagnostics", tags=["Diagnostico Automatico"])


@router.get("/run", response_model=DiagnosticsReportResponse)
def run_diagnostics(db: Session = Depends(get_db)):
    return DiagnosticsService(db).run_full_diagnostics()


@router.get("/checks/{name}", response_model=DiagnosticCheckResponse)
def run_single_check(name: str, db: Session = Depends(get_db)):
    try:
        check = DiagnosticsService(db).run_check(name)
    except UnknownDiagnosticCheckError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return check.to_dict()
