from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.agency_operator import AgencyWorkflowActionRequest, AgencyWorkflowCreateRequest, AgencyWorkflowListResponse, AgencyWorkflowResponse
from app.services.agency_operator import AgencyOperatorService

router = APIRouter(prefix="/agency-operator", tags=["AI Agency Operator"])


@router.post("/workflows", response_model=AgencyWorkflowResponse)
def create_workflow(payload: AgencyWorkflowCreateRequest, db: Session = Depends(get_db)):
    return AgencyOperatorService(db).create_workflow(payload)


@router.get("/workflows", response_model=AgencyWorkflowListResponse)
def list_workflows(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return AgencyOperatorService(db).list_workflows(limit=limit)


@router.post("/workflows/{workflow_id}/{action}", response_model=AgencyWorkflowResponse)
def transition_workflow(workflow_id: int, action: str, payload: AgencyWorkflowActionRequest, db: Session = Depends(get_db)):
    try:
        return AgencyOperatorService(db).transition(workflow_id, action, payload.notes or "")
    except ValueError as exc:
        raise HTTPException(status_code=404 if "não encontrado" in str(exc) else 400, detail=str(exc)) from exc
