from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.domain.models import User
from app.repositories.ad_repository import AdRepository
from app.repositories.decision_log_repository import DecisionLogRepository
from app.schemas.ads import AdAnalysisRequest, AdAnalysisResponse, DashboardSummary
from app.services.ad_processor import AdProcessor
from app.services.decision_feed import DecisionFeedService

router = APIRouter(prefix="/ads", tags=["Ads"])


@router.post("/analyze", response_model=AdAnalysisResponse, status_code=201)
def analyze_ad(payload: AdAnalysisRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repository = AdRepository(db)
    processor = AdProcessor(repository)
    analysis = processor.process(payload, user_id=current_user.id)
    DecisionFeedService(DecisionLogRepository(db)).register_analysis_decisions(analysis, user_id=current_user.id)
    return analysis


@router.get("/latest", response_model=list[AdAnalysisResponse])
def latest_ads(limit: int = 20, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return AdRepository(db).list_latest(limit, user_id=current_user.id)


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return AdRepository(db).summary(user_id=current_user.id)
