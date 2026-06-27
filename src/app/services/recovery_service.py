from __future__ import annotations

from datetime import datetime, timedelta, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import QueueJob
from app.services.queue_service import QueueService, serialize_job


class RecoveryService:
    """Missao 47 - Testes de Recuperacao.

    Contraparte de ACAO do health_report() da fila (Missao 42): aquele
    metodo so DETECTA jobs travados em "running" alem do lock timeout, e o
    proprio docstring de health_report() documenta a limitacao - esses
    jobs "serao reclamados no proximo claim()". Se nenhum worker estiver
    chamando claim() naquele momento (fila parada, worker caido, deploy em
    andamento), o job fica invisivel e parado indefinidamente, mesmo que o
    problema seja perfeitamente recuperavel. RecoveryService age agora,
    sem esperar pelo proximo claim()."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.queue_service = QueueService(db)

    def recovery_report(self) -> dict[str, Any]:
        """Somente leitura - reusa QueueService.health_report() (Missao
        42) e classifica o que e acionavel agora por
        recover_stale_running_jobs() (jobs travados em "running") versus
        o que exige intervencao externa (jobs "starving": fila sem nenhum
        worker puxando - religar um worker nao e algo que dados sozinhos
        resolvem)."""
        health = self.queue_service.health_report()
        return {
            "healthy": health["healthy"],
            "recoverable_now": len(health["stuck_jobs"]),
            "requires_external_action": len(health["starving_jobs"]),
            "warnings": health["warnings"],
        }

    def recover_stale_running_jobs(self, *, limit: int | None = None) -> dict[str, Any]:
        """Recupera AGORA os jobs travados em "running" alem do lock
        timeout (settings.queue_lock_timeout_seconds - mesmo limiar usado
        por health_report(), para que os dois nunca discordem sobre o que
        e "travado"). Job com tentativas restantes (attempts <
        max_attempts) volta para "retry" com next_attempt_at=agora
        (elegivel a reclaim imediato pelo proximo claim() - ja esperou o
        lock timeout inteiro, nao precisa de backoff adicional). Job sem
        tentativas restantes vai para "dead", mesma semantica de fail()
        (Missao 42) quando esgota as tentativas. Em ambos os casos,
        locked_by/locked_at sao limpos. `limit` (default:
        settings.recovery_max_jobs_per_sweep) protege contra varrer uma
        fila inteira de uma vez em produção."""

        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=self.settings.queue_lock_timeout_seconds)
        sweep_limit = limit if limit is not None else self.settings.recovery_max_jobs_per_sweep

        stuck_jobs = (
            self.db.query(QueueJob)
            .filter(QueueJob.status == "running", QueueJob.locked_at < stale_before)
            .order_by(QueueJob.locked_at.asc())
            .limit(sweep_limit)
            .all()
        )

        recovered_to_retry: list[dict[str, Any]] = []
        recovered_to_dead: list[dict[str, Any]] = []

        for job in stuck_jobs:
            stuck_since = job.locked_at
            previous_worker = job.locked_by
            if job.attempts < job.max_attempts:
                job.status = "retry"
                job.next_attempt_at = now
                job.error_message = (
                    f"Recuperado automaticamente (Missao 47): travado em 'running' desde "
                    f"{stuck_since.isoformat()} pelo worker '{previous_worker}', alem do lock "
                    f"timeout de {self.settings.queue_lock_timeout_seconds}s."
                )
            else:
                job.status = "dead"
                job.next_attempt_at = None
                job.error_message = (
                    f"Recuperado automaticamente (Missao 47): travado em 'running' sem tentativas "
                    f"restantes ({job.attempts}/{job.max_attempts})."
                )
            job.locked_by = ""
            job.locked_at = None
            job.updated_at = now
            self.db.commit()
            self.db.refresh(job)
            if job.status == "retry":
                recovered_to_retry.append(serialize_job(job))
            else:
                recovered_to_dead.append(serialize_job(job))

        return {
            "swept_at": now,
            "lock_timeout_seconds": self.settings.queue_lock_timeout_seconds,
            "found": len(stuck_jobs),
            "recovered_to_retry": recovered_to_retry,
            "recovered_to_dead": recovered_to_dead,
            "more_pending": len(stuck_jobs) == sweep_limit,
        }
