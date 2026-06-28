"""Missao 124 - Enterprise Quality Observatory.

Terceira missao da Fase v2.1. Diferente da Missao 60 (Enterprise
Readiness Certification, um GATE binario "pronto/nao pronto"), esta
missao constroi um OBSERVATORIO continuo: o criterio literal e
"qualidade acompanhada continuamente", nao "qualidade aprovada". Por
isso `quality_report()` nao produz um veredito unico bloqueante -
produz seis dimensoes monitoradas, cada uma com o sinal de saude mais
real que o motor correspondente ja calcula hoje, sem reimplementar
nenhum deles (regra 7 do CLAUDE.md).

As seis dimensoes pedidas e suas fontes reais, todas reaproveitadas
sem recalcular logica ja existente:

1. Bugs -> `AlertService.active_alerts()` (Missao 46). Um "bug" em
   producao, neste projeto, e exatamente o que a Missao 46 ja modela
   como AlertEvent aberto: um diagnostico que falhou e continua
   falhando. Reuso direto, sem reavaliar diagnosticos aqui.
2. Performance -> `ArchitectureStressTestService.stress_report()`
   (Missao 59). Reuso direto do veredito `clean` (latencia/falhas sob
   carga + isolamento de container).
3. Cobertura -> `EnterpriseReadinessService.mission_test_coverage()`
   (Missao 60). Reuso direto do metodo especifico - nao chama
   `readiness_report()` (que e a cadeia pesada e cara da Missao 60),
   so a checagem de cobertura de suite por missao.
4. Debito tecnico -> `TechDebtManagerService.debt_report()`
   (Missao 58). Reuso direto. Informativo, nunca bloqueante - mesma
   decisao de design ja documentada nas Missoes 58 e 60.
5. Estabilidade -> `RecoveryService.recovery_report()` (Missao 47, que
   por sua vez reusa `QueueService.health_report()` da Missao 42).
   Sinal real de saude operacional continua (fila de jobs travada,
   parada/inanicao, taxa de falha).
6. Seguranca -> `DependencyAuditService.audit()` (Missao 49). Reuso
   direto - superficie real de risco entre o que esta declarado em
   requirements.txt e o que esta de fato instalado.

Heuristica documentada (regra 7 do CLAUDE.md exige isso sempre que o
julgamento for qualitativo): para a dimensao de seguranca, tratamos
como BLOQUEANTE apenas `missing_count` e `version_mismatch_count`
(drift real entre declarado e instalado - risco concreto). NAO
tratamos `unpinned_count` como bloqueante aqui, porque a propria
Missao 49 documenta no modulo `dependency_audit_service.py` que hoje
19/19 dependencias estao sem pin por desenho conhecido do projeto -
tratar isso como bloqueio tornaria a dimensao sempre "doente" por um
motivo que a Missao 49 ja classificou como aviso, nao bloqueio. As
dependencias sem pin continuam visiveis em `security["issues"]` e em
`security["unpinned_count"]`, apenas nao derrubam o sinal de saude
desta dimensao.

Debito tecnico nao recebe um booleano de saude (`healthy: None` em
`monitored_dimensions["tech_debt"]`) de proposito: nao existe hoje, em
nenhuma missao anterior, um limiar oficial de "quantos itens de divida
sao aceitaveis" - inventar um aqui seria exatamente o tipo de
veredito decorativo que a regra 7 do CLAUDE.md proibe. O numero real
(`total_debt_items`) e exposto e acompanhado, mas sem fingir um
corte binario que nenhuma missao anterior definiu.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.alert_service import AlertService
from app.services.architecture_stress_test_service import ArchitectureStressTestService
from app.services.dependency_audit_service import DependencyAuditService
from app.services.enterprise_readiness_service import EnterpriseReadinessService
from app.services.recovery_service import RecoveryService
from app.services.tech_debt_manager_service import TechDebtManagerService

UTC = timezone.utc


class EnterpriseQualityObservatoryService:
    """Missao 124. Depende de `db` porque `AlertService`,
    `EnterpriseReadinessService` (transitivamente, mesmo motivo
    documentado na Missao 60) e `RecoveryService` precisam de banco.
    `ArchitectureStressTestService`, `TechDebtManagerService` e
    `DependencyAuditService` nao precisam, instanciados sem `db`,
    mesmo padrao das Missoes 58/59/49."""

    def __init__(
        self,
        db: Session,
        alert_service: AlertService | None = None,
        stress_test: ArchitectureStressTestService | None = None,
        enterprise_readiness: EnterpriseReadinessService | None = None,
        tech_debt_manager: TechDebtManagerService | None = None,
        recovery_service: RecoveryService | None = None,
        dependency_audit: DependencyAuditService | None = None,
    ) -> None:
        self.db = db
        self.alert_service = alert_service or AlertService(db)
        self.stress_test = stress_test or ArchitectureStressTestService()
        self.enterprise_readiness = enterprise_readiness or EnterpriseReadinessService(db)
        self.tech_debt_manager = tech_debt_manager or TechDebtManagerService()
        self.recovery_service = recovery_service or RecoveryService(db)
        self.dependency_audit = dependency_audit or DependencyAuditService()

    def bug_observatory(self) -> dict[str, Any]:
        """Bugs: AlertEvents abertos agora (Missao 46), sem reavaliar
        diagnosticos - so le o que ja esta registrado."""
        alerts = self.alert_service.active_alerts()
        by_severity: dict[str, int] = {}
        for alert in alerts:
            by_severity[alert["severity"]] = by_severity.get(alert["severity"], 0) + 1
        return {
            "active_alert_count": len(alerts),
            "by_severity": dict(sorted(by_severity.items())),
            "alerts": alerts,
            "clean": len(alerts) == 0,
        }

    def performance_observatory(self) -> dict[str, Any]:
        """Performance: reuso direto de
        ArchitectureStressTestService.stress_report() (Missao 59)."""
        return self.stress_test.stress_report()

    def coverage_observatory(self) -> dict[str, Any]:
        """Cobertura: reuso direto de
        EnterpriseReadinessService.mission_test_coverage() (Missao 60) -
        nunca chama o readiness_report() inteiro, so este metodo."""
        return self.enterprise_readiness.mission_test_coverage()

    def tech_debt_observatory(self) -> dict[str, Any]:
        """Debito tecnico: reuso direto de
        TechDebtManagerService.debt_report() (Missao 58)."""
        return self.tech_debt_manager.debt_report()

    def stability_observatory(self) -> dict[str, Any]:
        """Estabilidade: reuso direto de
        RecoveryService.recovery_report() (Missao 47), que por sua vez
        reusa QueueService.health_report() (Missao 42)."""
        return self.recovery_service.recovery_report()

    def security_observatory(self) -> dict[str, Any]:
        """Seguranca: reuso direto de DependencyAuditService.audit()
        (Missao 49), com o campo extra `clean` (heuristica documentada
        no docstring do modulo: missing_count + version_mismatch_count
        == 0; unpinned_count nao entra no bloqueio)."""
        audit = self.dependency_audit.audit()
        clean = audit["missing_count"] == 0 and audit["version_mismatch_count"] == 0
        return {**audit, "clean": clean}

    def quality_report(self) -> dict[str, Any]:
        """Leitura pura. Seis dimensoes monitoradas continuamente -
        SEM veredito unico bloqueante (essa e a diferenca deliberada
        frente a Missao 60: o criterio aqui e "acompanhada", nao
        "aprovada"). `tech_debt` nunca recebe healthy=True/False, so
        healthy=None + o numero real, pelo motivo documentado no
        docstring do modulo."""

        bugs = self.bug_observatory()
        performance = self.performance_observatory()
        coverage = self.coverage_observatory()
        tech_debt = self.tech_debt_observatory()
        stability = self.stability_observatory()
        security = self.security_observatory()

        monitored_dimensions: dict[str, dict[str, Any]] = {
            "bugs": {
                "healthy": bugs["clean"],
                "signal": "active_alert_count",
                "value": bugs["active_alert_count"],
            },
            "performance": {
                "healthy": performance["clean"],
                "signal": "stress_report.clean",
                "value": performance["clean"],
            },
            "coverage": {
                "healthy": coverage["complete"],
                "signal": "missions_without_dedicated_suite",
                "value": len(coverage["missions_without_dedicated_suite"]),
            },
            "tech_debt": {
                "healthy": None,
                "signal": "total_debt_items (informativo, nunca bloqueante - mesma decisao das Missoes 58/60)",
                "value": tech_debt["summary"]["total_debt_items"],
            },
            "stability": {
                "healthy": stability["healthy"],
                "signal": "queue_health.warnings",
                "value": len(stability["warnings"]),
            },
            "security": {
                "healthy": security["clean"],
                "signal": "missing_count+version_mismatch_count",
                "value": security["missing_count"] + security["version_mismatch_count"],
            },
        }

        healthy_dimensions = sorted(
            name for name, data in monitored_dimensions.items() if data["healthy"] is True
        )
        unhealthy_dimensions = sorted(
            name for name, data in monitored_dimensions.items() if data["healthy"] is False
        )
        untracked_dimensions = sorted(
            name for name, data in monitored_dimensions.items() if data["healthy"] is None
        )

        return {
            "generated_at": datetime.now(UTC),
            "monitored_dimensions": monitored_dimensions,
            "healthy_dimensions": healthy_dimensions,
            "unhealthy_dimensions": unhealthy_dimensions,
            "untracked_dimensions": untracked_dimensions,
            "bugs": bugs,
            "performance": performance,
            "coverage": coverage,
            "tech_debt": tech_debt,
            "stability": stability,
            "security": security,
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.quality_report()
        dims = report["monitored_dimensions"]

        lines: list[str] = [
            "# Observatorio de Qualidade Enterprise (Missao 124)",
            "",
            f"- Gerado em: {report['generated_at']}",
            "",
            "## Dimensoes monitoradas",
            "",
        ]
        for name, data in dims.items():
            if data["healthy"] is None:
                marker = "INFORMATIVO"
            elif data["healthy"]:
                marker = "OK"
            else:
                marker = "ATENCAO"
            lines.append(f"- `{name}`: {marker} ({data['signal']} = {data['value']})")

        lines.append("")
        lines.append(
            f"- Dimensoes saudaveis: {report['healthy_dimensions']}"
        )
        if report["unhealthy_dimensions"]:
            lines.append(
                f"- Dimensoes com atencao: {report['unhealthy_dimensions']}"
            )
        if report["untracked_dimensions"]:
            lines.append(
                f"- Dimensoes informativas (sem corte binario por desenho): "
                f"{report['untracked_dimensions']}"
            )

        lines.append("")
        lines.append(
            "**IMPORTANTE**: este observatorio acompanha qualidade continuamente "
            "(criterio da Missao 124), NAO substitui o gate binario de prontidao "
            "enterprise da Missao 60 nem a certificacao oficial da Fase Omega "
            "(O01-O10 + tag `v1.1.0` no remoto)."
        )

        return "\n".join(lines)
