from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import QueueJob

TERMINAL_STATUSES = {"done", "dead"}


class QueueService:
    """Zero-cost queue layer.

    Default backend is SQLite with WAL mode for personal/local usage. The public
    contract is intentionally Redis-like so the project can switch to KeyDB later
    without changing the calling services.
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    @property
    def backend(self) -> str:
        return self.settings.queue_backend

    def enqueue(self, *, queue_name: str, job_type: str, payload: dict[str, Any], priority: int = 100, max_attempts: int | None = None) -> QueueJob:
        job = QueueJob(
            queue_name=queue_name,
            job_type=job_type,
            status="queued",
            priority=priority,
            max_attempts=max_attempts or self.settings.queue_default_max_attempts,
            payload_json=json.dumps(payload, ensure_ascii=False),
            result_json="{}",
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def claim(self, *, queue_name: str = "default", worker_id: str = "local-worker", limit: int = 1) -> list[QueueJob]:
        now = datetime.now(UTC)
        lock_expired_before = now - timedelta(seconds=self.settings.queue_lock_timeout_seconds)

        jobs = (
            self.db.query(QueueJob)
            .filter(QueueJob.queue_name == queue_name)
            .filter(
                or_(
                    QueueJob.status == "queued",
                    (QueueJob.status == "running") & (QueueJob.locked_at < lock_expired_before),
                    QueueJob.status == "retry",
                )
            )
            .order_by(QueueJob.priority.asc(), QueueJob.created_at.asc())
            .limit(limit)
            .all()
        )

        for job in jobs:
            job.status = "running"
            job.locked_by = worker_id
            job.locked_at = now
            job.attempts += 1
            job.updated_at = now
        self.db.commit()
        for job in jobs:
            self.db.refresh(job)
        return jobs

    def complete(self, job_id: int, result: dict[str, Any] | None = None) -> QueueJob:
        job = self._get_job(job_id)
        job.status = "done"
        job.result_json = json.dumps(result or {}, ensure_ascii=False)
        job.error_message = ""
        job.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(job)
        return job

    def fail(self, job_id: int, error_message: str, retry: bool = True) -> QueueJob:
        job = self._get_job(job_id)
        if retry and job.attempts < job.max_attempts:
            job.status = "retry"
        else:
            job.status = "dead"
        job.error_message = error_message
        job.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_jobs(self, queue_name: str | None = None, status: str | None = None, limit: int = 50) -> list[QueueJob]:
        query = self.db.query(QueueJob)
        if queue_name:
            query = query.filter(QueueJob.queue_name == queue_name)
        if status:
            query = query.filter(QueueJob.status == status)
        return query.order_by(QueueJob.created_at.desc()).limit(limit).all()

    def stats(self) -> dict[str, Any]:
        rows = self.db.query(QueueJob.status, func.count(QueueJob.id)).group_by(QueueJob.status).all()
        counts = {status: count for status, count in rows}
        total = sum(counts.values())
        return {
            "backend": self.backend,
            "queued": counts.get("queued", 0) + counts.get("retry", 0),
            "running": counts.get("running", 0),
            "done": counts.get("done", 0),
            "failed": counts.get("failed", 0),
            "dead": counts.get("dead", 0),
            "total": total,
            "recommendation": self._recommendation(total),
        }

    def _recommendation(self, total: int) -> str:
        if self.backend == "sqlite" and total < 10000:
            return "SQLite WAL está adequado para uso pessoal e baixo volume."
        if self.backend == "sqlite":
            return "Considere KeyDB/PostgreSQL queue se o volume crescer acima de 10k jobs."
        if self.backend == "keydb":
            return "KeyDB está configurado para volume maior sem Redis gerenciado."
        return "Backend de fila configurado."

    def _get_job(self, job_id: int) -> QueueJob:
        job = self.db.get(QueueJob, job_id)
        if not job:
            raise ValueError(f"Queue job {job_id} não encontrado")
        return job


def serialize_job(job: QueueJob) -> dict[str, Any]:
    def safe_json(value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"raw": value}

    return {
        "id": job.id,
        "queue_name": job.queue_name,
        "job_type": job.job_type,
        "status": job.status,
        "priority": job.priority,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "payload": safe_json(job.payload_json),
        "result": safe_json(job.result_json),
        "error_message": job.error_message,
        "locked_by": job.locked_by,
        "locked_at": job.locked_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
