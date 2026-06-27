from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.platform_readiness import (
    decision_assistant,
    executive_audit_trail,
    executive_daily_briefing,
    final_flight_certification,
    knowledge_center,
    mission_analytics,
    performance_profiler,
    platform_readiness_certification,
    recovery_engine,
    self_diagnostic_engine,
    smart_alert_center,
    write_sigma_certification_report,
)
from app.db.session import get_db
from app.domain.models import User

router = APIRouter(prefix="/platform-readiness", tags=["Platform Readiness"])


@router.get("/self-diagnostic")
def get_self_diagnostic(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return self_diagnostic_engine(db)


@router.get("/recovery")
def get_recovery(current_user: User = Depends(get_current_user)):
    return recovery_engine()


@router.get("/performance")
def get_performance(current_user: User = Depends(get_current_user)):
    return performance_profiler()


@router.get("/mission-analytics")
def get_mission_analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return mission_analytics(db)


@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return smart_alert_center(db)


@router.get("/daily-briefing")
def get_daily_briefing(name: str = "Douglas", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return executive_daily_briefing(db, name=name)


@router.get("/knowledge-center")
def get_knowledge_center(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return knowledge_center(db)


@router.get("/decision-assistant")
def get_decision_assistant(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return decision_assistant(db)


@router.get("/audit-trail")
def get_audit_trail(current_user: User = Depends(get_current_user)):
    return executive_audit_trail()


@router.get("/certification")
def get_certification(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return platform_readiness_certification(db)


@router.post("/certification/report")
def create_certification_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    path = write_sigma_certification_report(db)
    return {"status": "created", "path": str(path)}


@router.get("/final-flight")
def get_final_flight(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return final_flight_certification(db)
