from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.resources import CleanupResultResponse, DiskUsageReportResponse, QueuePurgeResultResponse
from app.services.resource_manager_service import ResourceManagerService

router = APIRouter(prefix="/resources", tags=["Gerenciamento de Recursos"])


@router.get("/disk-usage", response_model=DiskUsageReportResponse)
def disk_usage(db: Session = Depends(get_db)):
    return ResourceManagerService(db).disk_usage_report()


@router.post("/queue-jobs/purge", response_model=QueuePurgeResultResponse)
def purge_queue_jobs(max_age_days: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)):
    return ResourceManagerService(db).purge_old_queue_jobs(max_age_days=max_age_days)


@router.post("/cleanup", response_model=CleanupResultResponse)
def run_cleanup(max_age_days: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)):
    return ResourceManagerService(db).run_cleanup(max_age_days=max_age_days)
