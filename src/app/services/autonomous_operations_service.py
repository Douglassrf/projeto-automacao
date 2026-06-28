from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.services.api_compatibility_service import ApiCompatibilityService
from app.services.architecture_evolution_service import ArchitectureEvolutionService
from app.services.certification_service import CertificationService
from app.services.continuous_quality_service import ContinuousQualityService
from app.services.data_integrity_service import DataIntegrityService
from app.services.operational_intelligence_service import (
    GLOBAL_CRITICAL,
    GLOBAL_DEGRADED,
    GLOBAL_HEALTHY,
    OperationalIntelligenceService,
)
from app.services.predictive_health_service import PredictiveHealthService
from app.services.resource_optimization_service import ResourceOptimizationService
from app.services.technical_knowledge_service import TechnicalKnowledgeService
from app.services.workflow_orchestrator_service import WorkflowOrchestratorService

UTC = timezone.utc

VERDICT_READY = "autonomous_operations_ready"
VERDICT_NOT_READY = "not_ready"
VERDICT_DEGRADED = "ready_with_caveats"

DOMAINS: tuple[dict[str, str], ...] = (
    {"domain": "governance", "source": "certification", "mission": "50"},
    {"domain": "observability", "source": "operational_intelligence", "mission": "71"},
    {"domain": "security", "source": "certification", "mission": "50"},
    {"domain": "recovery", "source": "operational_intelligence", "mission": "71"},
    {"domain": "quality", "source": "continuous_quality", "mission": "74"},
    {"domain": "documentation", "source": "technical_knowledge", "mission": "73"},
    {"domain": "compatibility", "source": "api_compatibility", "mission": "76"},
    {"domain": "data_integrity", "source": "data_integrity", "mission": "75"},
    {"domain": "orchestration", "source": "workflow_orchestrator", "mission": "77"},
    {"domain": "scalability", "source": "resource_optimization", "mission": "78"},
)


class AutonomousOperationsService:
    """Missao 80 - Autonomous Operations Readiness (CAPSTONE).

    Agrega M71-M79 + M41-M50 (via CertificationService e
    OperationalIntelligenceService) e valida dez dominios operacionais.
    Fail-closed: verdict so e READY se nenhum blocking_issue for encontrado
    e autonomous_ops_require_all_domains=True (gate padrao).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.certification = CertificationService(db)
        self.operational = OperationalIntelligenceService(db)
        self.predictive = PredictiveHealthService(db)
        self.knowledge = TechnicalKnowledgeService(db)
        self.quality = ContinuousQualityService(db)
        self.integrity = DataIntegrityService(db)
        self.compatibility = ApiCompatibilityService(db)
        self.workflow = WorkflowOrchestratorService(db)
        self.optimization = ResourceOptimizationService(db)
        self.architecture = ArchitectureEvolutionService(db)

    def _domain_status(
        self,
        *,
        certification: dict[str, Any],
        operational: dict[str, Any],
        quality: dict[str, Any],
        integrity: dict[str, Any],
        compatibility: dict[str, Any],
        workflow: dict[str, Any],
        optimization: dict[str, Any],
    ) -> dict[str, str]:
        ops_status = operational["global_project_state"]["overall_status"]
        return {
            "governance": "ok" if certification["platinum_certified"] or not certification["blocking_issues"] else "fail",
            "observability": "ok" if ops_status != GLOBAL_CRITICAL else "fail",
            "security": "ok" if not certification["blocking_issues"] else "fail",
            "recovery": "ok" if operational["stability"]["queue_recovery_healthy"] else "fail",
            "quality": "ok" if quality["release_report"]["gate_passed"] else "fail",
            "documentation": "ok",
            "compatibility": "ok" if compatibility["all_tests_passed"] else "fail",
            "data_integrity": "ok" if integrity["overall_status"] != "critical" else "fail",
            "orchestration": "ok" if workflow["queue_health"]["healthy"] else "fail",
            "scalability": "ok" if not optimization["queue_optimization"]["optimization_needed"] else "warning",
        }

    def _blocking_issues(
        self,
        *,
        certification: dict[str, Any],
        operational: dict[str, Any],
        quality: dict[str, Any],
        integrity: dict[str, Any],
        compatibility: dict[str, Any],
        domain_status: dict[str, str],
    ) -> list[str]:
        issues: list[str] = list(certification["blocking_issues"])
        if operational["global_project_state"]["overall_status"] == GLOBAL_CRITICAL:
            issues.append("Operational Intelligence Hub reporta status global critical.")
        if not quality["release_report"]["gate_passed"]:
            issues.append("Continuous Quality Gate nao aprovado para release.")
        if integrity["overall_status"] == "critical":
            issues.append("Data Integrity Framework reporta status critical.")
        if not compatibility["all_tests_passed"]:
            issues.append("API Compatibility Center: testes de compatibilidade falharam.")
        if self.settings.autonomous_ops_require_all_domains:
            for domain, status in domain_status.items():
                if status == "fail":
                    issues.append(f"Dominio '{domain}' nao atende criterios de prontidao.")
        return issues

    def _verdict(self, blocking_issues: list[str], operational_status: str) -> str:
        if blocking_issues:
            return VERDICT_NOT_READY
        if operational_status == GLOBAL_DEGRADED:
            return VERDICT_DEGRADED
        return VERDICT_READY

    def readiness_report(self) -> dict[str, Any]:
        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)

        certification = self.certification.certify()
        operational = self.operational.health_panel()
        predictive = self.predictive.monitor_report()
        knowledge = self.knowledge.knowledge_base()
        quality = self.quality.quality_report()
        integrity = self.integrity.integrity_report()
        compatibility = self.compatibility.compatibility_report()
        workflow = self.workflow.orchestration_report()
        optimization = self.optimization.optimization_report()
        architecture = self.architecture.evolution_report()

        domain_status = self._domain_status(
            certification=certification,
            operational=operational,
            quality=quality,
            integrity=integrity,
            compatibility=compatibility,
            workflow=workflow,
            optimization=optimization,
        )
        blocking_issues = self._blocking_issues(
            certification=certification,
            operational=operational,
            quality=quality,
            integrity=integrity,
            compatibility=compatibility,
            domain_status=domain_status,
        )
        ops_status = operational["global_project_state"]["overall_status"]
        verdict = self._verdict(blocking_issues, ops_status)
        if not self.settings.autonomous_ops_require_all_domains:
            verdict = VERDICT_NOT_READY

        domains_ok = sum(1 for s in domain_status.values() if s == "ok")

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "require_all_domains": self.settings.autonomous_ops_require_all_domains,
            "verdict": verdict,
            "autonomous_operations_ready": verdict == VERDICT_READY,
            "blocking_issues": blocking_issues,
            "blocking_issue_count": len(blocking_issues),
            "domain_status": domain_status,
            "domains_ok": domains_ok,
            "domains_total": len(DOMAINS),
            "domains_tracked": list(DOMAINS),
            "evidence": {
                "certification_platinum": certification["platinum_certified"],
                "operational_status": ops_status,
                "predictive_degradation": predictive["degradation_report"]["overall_status"],
                "quality_gate_passed": quality["release_report"]["gate_passed"],
                "integrity_status": integrity["overall_status"],
                "compatibility_tests_passed": compatibility["all_tests_passed"],
                "knowledge_modules": len(knowledge["module_catalog"]),
                "workflow_progress_pct": workflow.get("progress", {}).get("progress_pct", 0),
                "optimization_needed": optimization["queue_optimization"]["optimization_needed"],
                "architecture_complexity": architecture["complexity_indicators"]["complexity_level"],
            },
            "config_validation_issues": config_validation_issues,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.readiness_report()
        lines = [
            "# Autonomous Operations Readiness — Relatorio Final",
            "",
            f"- Veredito: **{report['verdict']}**",
            f"- Pronto: {report['autonomous_operations_ready']}",
            f"- Dominios OK: {report['domains_ok']}/{report['domains_total']}",
            f"- CONFIG: {report['config_schema_version']}",
            "",
            "## Blocking issues",
        ]
        if report["blocking_issues"]:
            for issue in report["blocking_issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("- Nenhum blocking issue encontrado.")
        lines.append("")
        lines.append("## Dominios")
        for domain, status in report["domain_status"].items():
            lines.append(f"- {domain}: {status}")
        lines.append("")
        lines.append("## Evidencias")
        for key, value in report["evidence"].items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
