from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.domain.models import User
from app.repositories.decision_log_repository import DecisionLogRepository
from app.schemas.decision_logs import DecisionLogImportResponse, DecisionLogResponse, DecisionHealthSummary
from app.services.decision_feed import DecisionFeedService
from app.services.decision_ingest import DecisionDataIngestService

router = APIRouter(prefix="/logs", tags=["Decision Logs"])


@router.get("/decisions", response_model=list[DecisionLogResponse])
def latest_decisions(
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DecisionLogRepository(db).list_latest(limit=limit, user_id=current_user.id)


@router.get("/decisions/health-summary", response_model=DecisionHealthSummary)
def decision_health_summary(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = DecisionLogRepository(db).list_latest(limit=limit, user_id=current_user.id)
    danger = sum(1 for item in records if item.severity == "danger")
    warning = sum(1 for item in records if item.severity == "warning")
    success = sum(1 for item in records if item.severity == "success")
    if danger:
        status = "critical"
        headline = "Atenção urgente"
        next_action = "Abra os cartões vermelhos primeiro e corrija o gargalo antes de escalar."
    elif warning:
        status = "attention"
        headline = "Conta em atenção"
        next_action = "Revise cartões amarelos antes de aumentar orçamento."
    elif success:
        status = "healthy"
        headline = "Conta saudável"
        next_action = "Mantenha monitoramento e escale apenas vencedores consistentes."
    else:
        status = "empty"
        headline = "Sem dados suficientes"
        next_action = "Importe CSV do Gerenciador ou rode uma análise para gerar decisões."
    return DecisionHealthSummary(total=len(records), success=success, warning=warning, danger=danger, info=sum(1 for item in records if item.severity == "info"), status=status, headline=headline, next_action=next_action)


@router.post("/decisions/import-csv", response_model=DecisionLogImportResponse)
async def import_decision_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = (await file.read()).decode("utf-8-sig")
    service = DecisionDataIngestService(DecisionFeedService(DecisionLogRepository(db)))
    result = service.import_csv_text(content, user_id=current_user.id)
    return DecisionLogImportResponse(**result.__dict__)


@router.post("/decisions/stress-test/crisis", response_model=list[DecisionLogResponse])
def run_crisis_stress_test(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = DecisionDataIngestService(DecisionFeedService(DecisionLogRepository(db)))
    return service.create_crisis_scenario(user_id=current_user.id)
