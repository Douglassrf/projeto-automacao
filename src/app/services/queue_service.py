from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from typing import Any
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import QueueJob

TERMINAL_STATUSES = {"done", "dead"}

# Amostra minima de jobs finalizados (done+dead) numa fila antes do
# health_report() calcular taxa de falha - evita alarme falso com 1 de 1.
_MIN_SAMPLE_FOR_FAILURE_RATE = 5


def compute_backoff_seconds(*, attempts: int, job_id: int, base_seconds: int, max_seconds: int) -> float:
    """Missao 42 - Gerenciador Inteligente de Filas.

    Backoff exponencial (base * 2**(attempts-1)), limitado por max_seconds,
    com jitter deterministico derivado do job_id (nao usa `random`, de
    proposito: o mesmo job sempre recalcula o mesmo valor, o que torna a
    funcao trivial de testar, e jobs diferentes ainda recebem atrasos
    levemente diferentes entre si - o suficiente para evitar que um lote de
    falhas simultaneas todas tentem de novo exatamente no mesmo instante."""

    attempts = max(1, attempts)
    base_seconds = max(0, base_seconds)
    exponential = base_seconds * (2 ** (attempts - 1))
    jitter = (job_id % base_seconds) if base_seconds > 0 else 0
    return float(min(exponential + jitter, max_seconds))


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
                    # Missao 42: um job "retry" so pode ser reclamado depois do
                    # seu backoff expirar (ou se nunca teve next_attempt_at).
                    (QueueJob.status == "retry")
                    & or_(QueueJob.next_attempt_at.is_(None), QueueJob.next_attempt_at <= now),
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
        job.next_attempt_at = None
        job.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(job)
        return job

    def fail(self, job_id: int, error_message: str, retry: bool = True) -> QueueJob:
        job = self._get_job(job_id)
        if retry and job.attempts < job.max_attempts:
            job.status = "retry"
            # Missao 42: backoff exponencial com jitter por job, em vez de
            # liberar o job para reclaim imediato (o que sobrecarregaria um
            # dependente externo instavel com retries de volta a volta).
            delay_seconds = compute_backoff_seconds(
                attempts=job.attempts,
                job_id=job.id,
                base_seconds=self.settings.queue_retry_backoff_base_seconds,
                max_seconds=self.settings.queue_retry_backoff_max_seconds,
            )
            job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        else:
            job.status = "dead"
            job.next_attempt_at = None
        job.error_message = error_message
        job.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(job)
        return job

    def requeue_dead_letter(self, job_id: int, *, reset_attempts: bool = True) -> QueueJob:
        """Missao 42: reenvio manual de um job morto (dead-letter) para a fila.

        Só aceita jobs com status "dead" - um job ainda em retry/running já
        tem seu próprio caminho de volta à fila e não deveria ser tocado por
        aqui, para não mascarar um bug de concorrência."""

        job = self._get_job(job_id)
        if job.status != "dead":
            raise ValueError(
                f"Queue job {job_id} não está 'dead' (status atual: '{job.status}'); "
                "só jobs mortos podem ser reenviados manualmente via requeue_dead_letter()."
            )
        job.status = "queued"
        job.next_attempt_at = None
        job.locked_by = ""
        job.locked_at = None
        if reset_attempts:
            job.attempts = 0
        job.error_message = f"[reenviado manualmente] {job.error_message}".strip()
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
        # Missao 42: sinal rapido de saude sem o payload pesado do
        # health_report() completo (sem listas de jobs) - para quem so
        # quer um pulso, nao um diagnostico.
        health = self.health_report()
        return {
            "backend": self.backend,
            "queued": counts.get("queued", 0) + counts.get("retry", 0),
            "running": counts.get("running", 0),
            "done": counts.get("done", 0),
            "failed": counts.get("failed", 0),
            "dead": counts.get("dead", 0),
            "total": total,
            "recommendation": self._recommendation(total),
            "healthy": health["healthy"],
            "warnings": health["warnings"],
        }

    def health_report(self) -> dict[str, Any]:
        """Missao 42: diagnostico de saude da fila.

        Detecta tres sinais que um worker sozinho nao enxerga:
        1) jobs travados em "running" alem do lock timeout (serao
           reclamados no proximo claim(), mas ate la ficam invisiveis);
        2) jobs esperando ha mais tempo que queue_starvation_threshold_seconds
           sem nunca terem sido executados (fila parada/inanicao);
        3) filas com taxa de falha (dead / (done+dead)) acima de
           queue_failure_rate_threshold, com amostra minima para evitar
           alarme falso com poucos jobs."""

        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=self.settings.queue_lock_timeout_seconds)
        starving_before = now - timedelta(seconds=self.settings.queue_starvation_threshold_seconds)

        stuck_jobs = (
            self.db.query(QueueJob)
            .filter(QueueJob.status == "running", QueueJob.locked_at < stale_before)
            .order_by(QueueJob.locked_at.asc())
            .all()
        )
        starving_jobs = (
            self.db.query(QueueJob)
            .filter(QueueJob.status.in_(["queued", "retry"]), QueueJob.created_at < starving_before)
            .order_by(QueueJob.created_at.asc())
            .all()
        )

        per_queue: dict[str, dict[str, int]] = {}
        for queue_name, status, count in (
            self.db.query(QueueJob.queue_name, QueueJob.status, func.count(QueueJob.id))
            .group_by(QueueJob.queue_name, QueueJob.status)
            .all()
        ):
            per_queue.setdefault(queue_name, {})[status] = count

        warnings: list[str] = []
        unhealthy_queues: list[str] = []
        for queue_name, counts in per_queue.items():
            done = counts.get("done", 0)
            dead = counts.get("dead", 0)
            finished = done + dead
            if finished >= _MIN_SAMPLE_FOR_FAILURE_RATE:
                failure_rate = dead / finished
                if failure_rate > self.settings.queue_failure_rate_threshold:
                    unhealthy_queues.append(queue_name)
                    warnings.append(
                        f"Fila '{queue_name}': taxa de falha {failure_rate:.0%} "
                        f"(limite {self.settings.queue_failure_rate_threshold:.0%}) - investigar."
                    )

        if stuck_jobs:
            warnings.append(
                f"{len(stuck_jobs)} job(s) travado(s) em 'running' alem do lock timeout "
                f"({self.settings.queue_lock_timeout_seconds}s) - serao reclamados no proximo claim()."
            )
        if starving_jobs:
            warnings.append(
                f"{len(starving_jobs)} job(s) esperando ha mais de "
                f"{self.settings.queue_starvation_threshold_seconds}s sem execucao - possivel inanicao/fila parada."
            )

        return {
            "healthy": not warnings,
            "stuck_jobs": [serialize_job(job) for job in stuck_jobs],
            "starving_jobs": [serialize_job(job) for job in starving_jobs],
            "unhealthy_queues": unhealthy_queues,
            "per_queue": per_queue,
            "warnings": warnings,
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
        "next_attempt_at": job.next_attempt_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
