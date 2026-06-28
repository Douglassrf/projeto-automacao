from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.container import get_queue_service
from app.schemas.queue import (
    QueueClaimRequest,
    QueueCompleteRequest,
    QueueFailRequest,
    QueueHealthResponse,
    QueueJobCreate,
    QueueJobResponse,
    QueueRequeueRequest,
    QueueStatsResponse,
)
from app.services.queue_service import QueueService, serialize_job

router = APIRouter(prefix="/queue", tags=["Zero-Cost Queue"])


@router.post("/jobs", response_model=QueueJobResponse)
def enqueue_job(payload: QueueJobCreate, queue: QueueService = Depends(get_queue_service)):
    job = queue.enqueue(
        queue_name=payload.queue_name,
        job_type=payload.job_type,
        payload=payload.payload,
        priority=payload.priority,
        max_attempts=payload.max_attempts,
    )
    return serialize_job(job)


@router.post("/jobs/claim", response_model=list[QueueJobResponse])
def claim_jobs(payload: QueueClaimRequest, queue: QueueService = Depends(get_queue_service)):
    jobs = queue.claim(queue_name=payload.queue_name, worker_id=payload.worker_id, limit=payload.limit)
    return [serialize_job(job) for job in jobs]


@router.post("/jobs/{job_id}/complete", response_model=QueueJobResponse)
def complete_job(job_id: int, payload: QueueCompleteRequest, queue: QueueService = Depends(get_queue_service)):
    try:
        job = queue.complete(job_id, payload.result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_job(job)


@router.post("/jobs/{job_id}/fail", response_model=QueueJobResponse)
def fail_job(job_id: int, payload: QueueFailRequest, queue: QueueService = Depends(get_queue_service)):
    try:
        job = queue.fail(job_id, payload.error_message, payload.retry)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_job(job)


@router.get("/jobs", response_model=list[QueueJobResponse])
def list_jobs(
    queue_name: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    queue: QueueService = Depends(get_queue_service),
):
    jobs = queue.list_jobs(queue_name=queue_name, status=status, limit=limit)
    return [serialize_job(job) for job in jobs]


@router.get("/stats", response_model=QueueStatsResponse)
def queue_stats(queue: QueueService = Depends(get_queue_service)):
    return queue.stats()


@router.get("/health", response_model=QueueHealthResponse)
def queue_health(queue: QueueService = Depends(get_queue_service)):
    """Missao 42 - Gerenciador Inteligente de Filas: diagnostico de saude."""
    return queue.health_report()


@router.post("/jobs/{job_id}/requeue", response_model=QueueJobResponse)
def requeue_dead_letter_job(
    job_id: int, payload: QueueRequeueRequest, queue: QueueService = Depends(get_queue_service)
):
    """Missao 42: reenvia manualmente um job dead-letter para a fila."""
    try:
        job = queue.requeue_dead_letter(job_id, reset_attempts=payload.reset_attempts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_job(job)
