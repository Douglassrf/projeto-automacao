from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.workflow_orchestrator import WorkflowOrchestratorResponse
from app.services.workflow_orchestrator_service import WorkflowOrchestratorService

router = APIRouter(prefix="/workflow-orchestrator", tags=["Workflow Orchestrator"])


@router.get("/status/live", response_model=WorkflowOrchestratorResponse)
def workflow_orchestrator_status_live(db: Session = Depends(get_db)):
    return WorkflowOrchestratorService(db).orchestration_report()


@router.get("/status/markdown", response_class=PlainTextResponse)
def workflow_orchestrator_status_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(
        content=WorkflowOrchestratorService(db).render_markdown(),
        media_type="text/markdown",
    )
