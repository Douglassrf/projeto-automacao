from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.services.alert_service import AlertService
from app.services.cache_service import CacheService
from app.services.certification_service import CertificationService
from app.services.dependency_audit_service import DependencyAuditService
from app.services.diagnostics_service import STATUS_CRITICAL, STATUS_OK, STATUS_WARNING
from app.services.diagnostics_service import DiagnosticsService
from app.services.queue_service import QueueService
from app.services.recovery_service import RecoveryService
from app.services.resource_manager_service import ResourceManagerService

GLOBAL_HEALTHY = "healthy"
GLOBAL_DEGRADED = "degraded"
GLOBAL_CRITICAL = "critical"

MODULES_TRACKED: tuple[dict[str, str], ...] = (
    {"module": "diagnostics", "mission": "44", "label": "Diagnostico Automatico"},
    {"module": "alerts", "mission": "46", "label": "Sistema de Alertas"},
    {"module": "cache", "mission": "43", "label": "Cache Inteligente"},
    {"module": "queue", "mission": "42", "label": "Fila Inteligente"},
    {"module": "resources", "mission": "45", "label": "Gerenciamento de Recursos"},
    {"module": "recovery", "mission": "47", "label": "Testes de Recuperacao"},
    {"module": "dependency_audit", "mission": "49", "label": "Auditoria de Dependencias"},
    {"module": "certification", "mission": "50", "label": "Certificacao Platinum"},
)


class OperationalIntelligenceService:
    """Missao 71 - Operational Intelligence Hub.

    Painel unificado de inteligencia operacional: consolida metricas ja
    calculadas por DiagnosticsService (M44), AlertService (M46),
    CacheService (M43), QueueService (M42), ResourceManagerService (M45),
    RecoveryService (M47), DependencyAuditService (M49) e
    CertificationService (M50) — sem reimplementar nenhuma logica deles.

    Estritamente de LEITURA: nenhum metodo aqui escreve no banco. AlertService
    e CertificationService sao consultados apenas via metodos read-only
    (`active_alerts()`, `certify()` — que por sua vez so le).

    Retorna quatro eixos do painel:
    - `global_project_state`: veredito agregado do projeto agora.
    - `stability`: sinais de estabilidade (diagnosticos, fila, alertas).
    - `performance`: sinais de desempenho (cache hit-rate, fila, disco).
    - `risk_indicators`: riscos conhecidos (dependencias, config, bloqueios).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.diagnostics = DiagnosticsService(db)
        self.alerts = AlertService(db)
        self.cache = CacheService(db)
        self.queue = QueueService(db)
        self.resources = ResourceManagerService(db)
        self.recovery = RecoveryService(db)
        self.dependency_audit = DependencyAuditService()
        self.certification = CertificationService(db)

    def _module_health(
        self,
        *,
        diagnostics: dict[str, Any],
        active_alerts: list[dict[str, Any]],
        cache_stats: dict[str, Any],
        queue_health: dict[str, Any],
        queue_recovery: dict[str, Any],
        dependency_audit: dict[str, Any],
        certification: dict[str, Any],
    ) -> dict[str, str]:
        return {
            "diagnostics": diagnostics["status"],
            "alerts": STATUS_OK if not active_alerts else STATUS_WARNING,
            "cache": STATUS_OK,
            "queue": STATUS_OK if queue_health["healthy"] else STATUS_WARNING,
            "resources": STATUS_OK,
            "recovery": STATUS_OK if queue_recovery["healthy"] else STATUS_WARNING,
            "dependency_audit": (
                STATUS_CRITICAL
                if dependency_audit["missing_count"] > 0
                or dependency_audit["version_mismatch_count"] > 0
                else STATUS_WARNING
                if dependency_audit["unpinned_count"] > 0
                and self.settings.operational_intelligence_include_unpinned_in_risk
                else STATUS_OK
            ),
            "certification": (
                STATUS_OK if certification["platinum_certified"] else STATUS_WARNING
            ),
        }

    def _overall_status(
        self,
        *,
        diagnostics_status: str,
        active_alerts_count: int,
        queue_recovery_healthy: bool,
        dependency_audit: dict[str, Any],
        blocking_issues: list[str],
        config_validation_issues: list[str],
    ) -> str:
        if diagnostics_status == STATUS_CRITICAL:
            return GLOBAL_CRITICAL
        if dependency_audit["missing_count"] > 0 or dependency_audit["version_mismatch_count"] > 0:
            return GLOBAL_CRITICAL
        if not queue_recovery_healthy:
            return GLOBAL_CRITICAL
        if blocking_issues:
            return GLOBAL_CRITICAL
        if diagnostics_status == STATUS_WARNING or active_alerts_count > 0:
            return GLOBAL_DEGRADED
        if config_validation_issues:
            return GLOBAL_DEGRADED
        if (
            self.settings.operational_intelligence_include_unpinned_in_risk
            and dependency_audit["unpinned_count"] > 0
        ):
            return GLOBAL_DEGRADED
        return GLOBAL_HEALTHY

    def _risk_indicators(
        self,
        *,
        dependency_audit: dict[str, Any],
        config_validation_issues: list[str],
        blocking_issues: list[str],
        resource_usage: dict[str, Any],
    ) -> dict[str, Any]:
        risks: list[str] = list(blocking_issues)
        risks.extend(config_validation_issues)

        if dependency_audit["missing_count"] > 0:
            risks.append(
                f"{dependency_audit['missing_count']} dependencia(s) declarada(s) ausente(s) do ambiente."
            )
        if dependency_audit["version_mismatch_count"] > 0:
            risks.append(
                f"{dependency_audit['version_mismatch_count']} dependencia(s) com versao divergente."
            )
        if (
            self.settings.operational_intelligence_include_unpinned_in_risk
            and dependency_audit["unpinned_count"] > 0
        ):
            risks.append(
                f"{dependency_audit['unpinned_count']} dependencia(s) sem versao fixa em requirements.txt."
            )

        return {
            "risk_count": len(risks),
            "risks": risks,
            "dependency_missing_count": dependency_audit["missing_count"],
            "dependency_version_mismatch_count": dependency_audit["version_mismatch_count"],
            "dependency_unpinned_count": dependency_audit["unpinned_count"],
            "config_validation_issue_count": len(config_validation_issues),
            "blocking_issue_count": len(blocking_issues),
            "disk_total_size_mb": resource_usage["total_size_mb"],
        }

    def _stability_indicators(
        self,
        *,
        diagnostics: dict[str, Any],
        active_alerts: list[dict[str, Any]],
        queue_health: dict[str, Any],
        queue_recovery: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "diagnostics_status": diagnostics["status"],
            "diagnostics_summary": diagnostics["summary"],
            "active_alerts_count": len(active_alerts),
            "queue_healthy": queue_health["healthy"],
            "queue_recovery_healthy": queue_recovery["healthy"],
            "stuck_jobs_count": len(queue_health.get("stuck_jobs", [])),
            "starving_jobs_count": len(queue_health.get("starving_jobs", [])),
            "recoverable_now": queue_recovery.get("recoverable_now", 0),
            "requires_external_action": queue_recovery.get("requires_external_action", 0),
        }

    def _performance_indicators(
        self,
        *,
        cache_stats: dict[str, Any],
        queue_health: dict[str, Any],
        resource_usage: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "cache_backend": cache_stats["backend"],
            "cache_hit_rate": cache_stats["hit_rate"],
            "cache_size": cache_stats["size"],
            "cache_live_size": cache_stats["live_size"],
            "cache_hits": cache_stats["hits"],
            "cache_misses": cache_stats["misses"],
            "queue_per_queue": queue_health.get("per_queue", {}),
            "queue_unhealthy_queues": queue_health.get("unhealthy_queues", []),
            "disk_total_size_mb": resource_usage["total_size_mb"],
            "disk_directories": resource_usage["directories"],
        }

    def health_panel(self) -> dict[str, Any]:
        """Consolida o painel unificado de inteligencia operacional."""

        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)

        diagnostics = self.diagnostics.run_full_diagnostics()
        active_alerts = self.alerts.active_alerts()
        cache_stats = self.cache.stats()
        queue_health = self.queue.health_report()
        queue_recovery = self.recovery.recovery_report()
        resource_usage = self.resources.disk_usage_report()
        dependency_audit = self.dependency_audit.audit()
        certification = self.certification.certify()

        module_health = self._module_health(
            diagnostics=diagnostics,
            active_alerts=active_alerts,
            cache_stats=cache_stats,
            queue_health=queue_health,
            queue_recovery=queue_recovery,
            dependency_audit=dependency_audit,
            certification=certification,
        )
        modules_ok = sum(1 for status in module_health.values() if status == STATUS_OK)

        overall_status = self._overall_status(
            diagnostics_status=diagnostics["status"],
            active_alerts_count=len(active_alerts),
            queue_recovery_healthy=queue_recovery["healthy"],
            dependency_audit=dependency_audit,
            blocking_issues=certification["blocking_issues"],
            config_validation_issues=config_validation_issues,
        )

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "include_unpinned_in_risk": self.settings.operational_intelligence_include_unpinned_in_risk,
            "global_project_state": {
                "overall_status": overall_status,
                "platinum_certified": certification["platinum_certified"],
                "diagnostics_status": diagnostics["status"],
                "modules_tracked": len(MODULES_TRACKED),
                "modules_healthy": modules_ok,
                "modules_health": module_health,
            },
            "stability": self._stability_indicators(
                diagnostics=diagnostics,
                active_alerts=active_alerts,
                queue_health=queue_health,
                queue_recovery=queue_recovery,
            ),
            "performance": self._performance_indicators(
                cache_stats=cache_stats,
                queue_health=queue_health,
                resource_usage=resource_usage,
            ),
            "risk_indicators": self._risk_indicators(
                dependency_audit=dependency_audit,
                config_validation_issues=config_validation_issues,
                blocking_issues=certification["blocking_issues"],
                resource_usage=resource_usage,
            ),
            "modules_tracked": list(MODULES_TRACKED),
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.health_panel()
        gps = report["global_project_state"]
        stability = report["stability"]
        performance = report["performance"]
        risk = report["risk_indicators"]

        lines: list[str] = []
        lines.append("# Operational Intelligence Hub - Painel de Saude")
        lines.append("")
        lines.append(f"- Gerado em: {report['generated_at']}")
        lines.append(f"- Ambiente: {report['environment']}")
        lines.append(f"- CONFIG_SCHEMA_VERSION: {report['config_schema_version']}")
        lines.append(f"- Status global: **{gps['overall_status']}**")
        lines.append(f"- Platinum certificado: {gps['platinum_certified']}")
        lines.append(
            f"- Modulos saudaveis: {gps['modules_healthy']}/{gps['modules_tracked']}"
        )
        lines.append("")

        lines.append("## Estabilidade")
        lines.append("")
        lines.append(f"- Diagnosticos: {stability['diagnostics_status']}")
        lines.append(f"- Alertas ativos: {stability['active_alerts_count']}")
        lines.append(f"- Fila saudavel: {stability['queue_healthy']}")
        lines.append(f"- Recuperacao de fila saudavel: {stability['queue_recovery_healthy']}")
        lines.append("")

        lines.append("## Desempenho")
        lines.append("")
        lines.append(
            f"- Cache ({performance['cache_backend']}): hit-rate "
            f"{performance['cache_hit_rate']:.0%}, "
            f"{performance['cache_live_size']}/{performance['cache_size']} entradas vivas"
        )
        lines.append(f"- Disco total gerenciado: {performance['disk_total_size_mb']} MB")
        lines.append("")

        lines.append("## Indicadores de risco")
        lines.append("")
        if risk["risks"]:
            for item in risk["risks"]:
                lines.append(f"- {item}")
        else:
            lines.append("- Nenhum risco identificado no painel agregado.")
        lines.append("")

        lines.append("## Modulos rastreados")
        lines.append("")
        for module in report["modules_tracked"]:
            health = gps["modules_health"][module["module"]]
            lines.append(
                f"- {module['label']} (Missao {module['mission']}): {health}"
            )
        lines.append("")

        return "\n".join(lines)
