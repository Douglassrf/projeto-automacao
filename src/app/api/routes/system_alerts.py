from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.system_alerts import AlertEvaluationResponse, AlertEventResponse
from app.services.alert_service import AlertService

router = APIRouter(prefix="/system-alerts", tags=["Sistema de Alertas"])


@router.post("/evaluate", response_model=AlertEvaluationResponse)
def evaluate_alerts(db: Session = Depends(get_db)):
    return AlertService(db).evaluate()


@router.get("/active", response_model=list[AlertEventResponse])
def active_alerts(db: Session = Depends(get_db)):
    return AlertService(db).active_alerts()


@router.get("/history", response_model=list[AlertEventResponse])
def alert_history(limit: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)):
    return AlertService(db).history(limit=limit)
