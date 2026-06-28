from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.services.queue_service import QueueService
from app.services.resource_manager_service import ResourceManagerService

UTC = timezone.utc


class ResourceOptimizationService:
    """Missao 78 - Resource Optimization Engine.

    Balanceamento de carga, otimizacao de filas e reducao de desperdicio.
    Reutiliza QueueService (M42) e ResourceManagerService (M45).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.queue = QueueService(db)
        self.resources = ResourceManagerService(db)

    def _load_balance_recommendations(self, queue_health: dict[str, Any]) -> list[str]:
        recs: list[str] = []
        per_queue = queue_health.get("per_queue", {})
        if not per_queue:
            return recs
        counts = {name: data.get("queued", 0) for name, data in per_queue.items()}
        if not counts:
            return recs
        max_q = max(counts, key=counts.get)
        min_q = min(counts, key=counts.get)
        if counts[max_q] - counts[min_q] > 5 and self.settings.resource_optimization_enable_rebalance:
            recs.append(
                f"Rebalancear carga: fila '{max_q}' ({counts[max_q]} queued) "
                f"vs '{min_q}' ({counts[min_q]} queued)."
            )
        return recs

    def _queue_optimization(self, queue_health: dict[str, Any]) -> dict[str, Any]:
        stuck = len(queue_health.get("stuck_jobs", []))
        starving = len(queue_health.get("starving_jobs", []))
        return {
            "stuck_jobs": stuck,
            "starving_jobs": starving,
            "optimization_needed": stuck > 0 or starving > 0,
            "suggestions": (
                ["Executar recovery sweep para jobs travados"] if stuck else []
            )
            + (["Revisar starvation threshold"] if starving else []),
        }

    def _waste_reduction(self, disk_report: dict[str, Any]) -> dict[str, Any]:
        total_mb = disk_report["total_size_mb"]
        return {
            "managed_disk_mb": total_mb,
            "waste_detected": total_mb > 1000,
            "recommendation": (
                "Executar limpeza de jobs terminais e cache expirado"
                if total_mb > 100
                else "Uso de disco dentro do esperado"
            ),
        }

    def optimization_report(self) -> dict[str, Any]:
        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)
        queue_health = self.queue.health_report()
        disk_report = self.resources.disk_usage_report()
        rebalance = self._load_balance_recommendations(queue_health)
        queue_opt = self._queue_optimization(queue_health)
        waste = self._waste_reduction(disk_report)

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "enable_rebalance": self.settings.resource_optimization_enable_rebalance,
            "load_balance_recommendations": rebalance,
            "queue_optimization": queue_opt,
            "waste_reduction": waste,
            "queue_health": queue_health,
            "disk_usage": disk_report,
            "config_validation_issues": config_validation_issues,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.optimization_report()
        lines = [
            "# Resource Optimization Engine",
            "",
            f"- Disco gerenciado: {report['waste_reduction']['managed_disk_mb']} MB",
            f"- Otimizacao fila necessaria: {report['queue_optimization']['optimization_needed']}",
            "",
        ]
        for rec in report["load_balance_recommendations"]:
            lines.append(f"- {rec}")
        return "\n".join(lines)
