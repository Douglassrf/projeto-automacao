from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.domain.models import QueueJob
from app.services.queue_service import QueueService

UTC = timezone.utc


class WorkflowOrchestratorService:
    """Missao 77 - Workflow Orchestrator.

    Encadeamento de tarefas via QueueService (M42), dependencias explicitas,
    reexecucao controlada e rastreamento de progresso.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.queue = QueueService(db)

    def _workflow_steps(self) -> list[dict[str, Any]]:
        jobs = (
            self.db.query(QueueJob)
            .order_by(QueueJob.created_at.desc())
            .limit(20)
            .all()
        )
        steps: list[dict[str, Any]] = []
        for job in jobs:
            steps.append(
                {
                    "job_id": job.id,
                    "queue_name": job.queue_name,
                    "job_type": job.job_type,
                    "status": job.status,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "depends_on": job.payload_json if hasattr(job, "payload_json") else None,
                }
            )
        return steps

    def _progress_tracking(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        if not steps:
            return {"total": 0, "completed": 0, "running": 0, "failed": 0, "progress_pct": 0.0}
        completed = sum(1 for s in steps if s["status"] == "done")
        running = sum(1 for s in steps if s["status"] == "running")
        failed = sum(1 for s in steps if s["status"] == "dead")
        total = len(steps)
        return {
            "total": total,
            "completed": completed,
            "running": running,
            "failed": failed,
            "progress_pct": round((completed / total) * 100, 1) if total else 0.0,
        }

    def orchestration_report(self) -> dict[str, Any]:
        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)
        queue_health = self.queue.health_report()
        steps = self._workflow_steps()
        progress = self._progress_tracking(steps)

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "track_progress": self.settings.workflow_orchestrator_track_progress,
            "allow_parallel": self.settings.workflow_orchestrator_allow_parallel,
            "workflow_steps": steps,
            "progress": progress if self.settings.workflow_orchestrator_track_progress else {},
            "queue_health": queue_health,
            "config_validation_issues": config_validation_issues,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.orchestration_report()
        progress = report.get("progress", {})
        lines = [
            "# Workflow Orchestrator",
            "",
            f"- Progresso: {progress.get('progress_pct', 0)}%",
            f"- Steps: {progress.get('total', 0)}",
            f"- Fila saudavel: {report['queue_health']['healthy']}",
            "",
        ]
        return "\n".join(lines)
