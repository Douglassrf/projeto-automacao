from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.domain.models import User
from app.core.mission_orchestrator import (
    mission_dashboard,
    mission_memory,
    mission_plan,
    mission_recovery,
    mission_score,
    mission_timeline,
)

router = APIRouter(prefix="/mission-orchestrator", tags=["Mission Orchestrator"])


@router.get("/planner")
def get_mission_planner(mission_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return mission_plan(db, mission_id)


@router.get("/timeline/{mission_id}")
def get_mission_timeline(mission_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return mission_timeline(db, mission_id)


@router.get("/memory")
def get_mission_memory(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return mission_memory(db, limit)


@router.get("/recovery/{mission_id}")
def get_mission_recovery(mission_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return mission_recovery(db, mission_id)


@router.get("/score")
def get_mission_score(mission_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return mission_score(db, mission_id)


@router.get("/dashboard/ui")
def get_mission_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return mission_dashboard(db)
