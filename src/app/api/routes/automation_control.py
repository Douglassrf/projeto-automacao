from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.db.session import get_db
from app.domain.models import User
from app.schemas.automation_control import (
    ApplySuggestionRequest,
    ApplySuggestionResponse,
    AutomationControlStatusResponse,
    KillSwitchRequest,
    KillSwitchResponse,
)
from app.services.automation_control import AutomationControlService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/automation-control", tags=["Automation Control"])


@router.get("/status", response_model=AutomationControlStatusResponse)
def automation_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return AutomationControlService(db).status()


@router.post("/apply-suggestion", response_model=ApplySuggestionResponse)
def apply_suggestion(payload: ApplySuggestionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return AutomationControlService(db).apply_suggestion(payload, user_id=current_user.id if current_user else None)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Falha ao aplicar sugestão: {exc}") from exc


@router.post("/kill-switch", response_model=KillSwitchResponse)
def set_kill_switch(payload: KillSwitchRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return AutomationControlService(db).set_kill_switch(payload.enabled, payload.reason)
