from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.queue import (
    QueueClaimRequest,
    QueueCompleteRequest,
    QueueFailRequest,
    QueueJobCreate,
    QueueJobResponse,
    QueueStatsResponse,
)
from app.services.queue_service import QueueService, serialize_job

router = APIRouter(prefix="/queue", tags=["Zero-Cost Queue"])


@router.post("/jobs", response_model=QueueJobResponse)
def enqueue_job(payload: QueueJobCreate, db: Session = Depends(get_db)):
    job = QueueService(db).enqueue(
        queue_name=payload.queue_name,
        job_type=payload.job_type,
        payload=payload.payload,
        priority=payload.priority,
        max_attempts=payload.max_attempts,
    )
    return serialize_job(job)


@router.post("/jobs/claim", response_model=list[QueueJobResponse])
def claim_jobs(payload: QueueClaimRequest, db: Session = Depends(get_db)):
    jobs = QueueService(db).claim(queue_name=payload.queue_name, worker_id=payload.worker_id, limit=payload.limit)
    return [serialize_job(job) for job in jobs]


@router.post("/jobs/{job_id}/complete", response_model=QueueJobResponse)
def complete_job(job_id: int, payload: QueueCompleteRequest, db: Session = Depends(get_db)):
    try:
        job = QueueService(db).complete(job_id, payload.result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_job(job)


@router.post("/jobs/{job_id}/fail", response_model=QueueJobResponse)
def fail_job(job_id: int, payload: QueueFailRequest, db: Session = Depends(get_db)):
    try:
        job = QueueService(db).fail(job_id, payload.error_message, payload.retry)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_job(job)


@router.get("/jobs", response_model=list[QueueJobResponse])
def list_jobs(
    queue_name: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    jobs = QueueService(db).list_jobs(queue_name=queue_name, status=status, limit=limit)
    return [serialize_job(job) for job in jobs]


@router.get("/stats", response_model=QueueStatsResponse)
def queue_stats(db: Session = Depends(get_db)):
    return QueueService(db).stats()
