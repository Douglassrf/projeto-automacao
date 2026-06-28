from __future__ import annotations

from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.services.alert_service import AlertService
from app.services.dependency_audit_service import DependencyAuditService
from app.services.diagnostics_service import STATUS_OK, DiagnosticsService
from app.services.recovery_service import RecoveryService
from app.services.resource_manager_service import ResourceManagerService

# Missoes cobertas por esta certificacao - apenas metadados descritivos,
# nao reimplementam nada das missoes citadas (ver atributos abaixo).
MISSIONS_COVERED: tuple[dict[str, str], ...] = (
    {
        "mission": "41",
        "name": "Configuracao Centralizada",
        "summary": "Perfis de ambiente, validate_settings() e CONFIG_SCHEMA_VERSION.",
    },
    {
        "mission": "42",
        "name": "Gerenciador Inteligente de Filas",
        "summary": "QueueService: enqueue/claim/retry/dead-letter, health_report().",
    },
    {
        "mission": "43",
        "name": "Cache Inteligente",
        "summary": "CacheService: TTL, namespaces, estatisticas de hit/miss.",
    },
    {
        "mission": "44",
        "name": "Diagnostico Automatico",
        "summary": "DiagnosticsService: checks de database/queue/cache/config/disk.",
    },
    {
        "mission": "45",
        "name": "Gerenciamento de Recursos",
        "summary": "ResourceManagerService: limpeza de jobs/cache, uso de disco.",
    },
    {
        "mission": "46",
        "name": "Sistema de Alertas",
        "summary": "AlertService: abre/atualiza/resolve AlertEvent a partir dos diagnosticos.",
    },
    {
        "mission": "47",
        "name": "Testes de Recuperacao",
        "summary": "RecoveryService: recupera jobs travados em 'running'.",
    },
    {
        "mission": "48",
        "name": "Documentacao Viva",
        "summary": "DocumentationService: snapshot de rotas/config gerado em tempo real.",
    },
    {
        "mission": "49",
        "name": "Auditoria de Dependencias",
        "summary": "DependencyAuditService: dependencias nao fixadas/ausentes/divergentes.",
    },
)


class CertificationService:
    """Missao 50 - Certificacao Platinum v1.3.

    Capstone das Missoes 41-49: NAO reimplementa nenhuma logica de
    diagnostico/alerta/fila/recurso/dependencia - apenas agrega, em uma
    unica chamada, o resultado ja calculado por cada servico anterior e
    aplica uma unica regra de veredito (`platinum_certified`).

    Esta classe e estritamente de LEITURA: nenhum metodo aqui escreve no
    banco (AlertService.evaluate(), que abre/resolve AlertEvent, e
    deliberadamente NAO chamado - so AlertService.active_alerts(), que e
    leitura pura, e usado). Rodar a certificacao repetidamente nunca
    produz efeito colateral.

    Regra de veredito ("fail-closed" por design):

    - `certification_platinum_require_clean_diagnostics` (Settings, Missao
      50) e o "gate". Quando True (padrao), `platinum_certified` so pode
      ser True se NENHUM dos `blocking_issues` abaixo for encontrado.
      Quando False, `platinum_certified` e SEMPRE False - desligar o gate
      nunca libera uma certificacao "de gracinha"; ele so reporta os
      mesmos `blocking_issues` (para transparencia) sem nunca aprovar.
      Ver validate_settings() em config_profiles.py: desligar este gate em
      producao e tratado como problema de configuracao.

    - `blocking_issues` (sempre calculado, independente do gate):
        1. `diagnostics_status != "ok"` (Missao 44 - cobre db/queue/cache/
           config/disk de uma vez, reaproveitando o `_worst()` ja
           calculado por `run_full_diagnostics()`).
        2. Qualquer alerta aberto (`AlertService.active_alerts()`, Missao
           46) - um problema conhecido e ainda nao resolvido.
        3. `dependency_audit.missing_count > 0` ou `.version_mismatch_count
           > 0` (Missao 49) - dependencia ausente do ambiente ou com
           versao instalada diferente da fixada. Deliberadamente NAO
           bloqueia em `unpinned_count` (ver M49_AUDITORIA_DEPENDENCIAS_
           REPORT.md): falta de pin e informativo/aceito como risco
           conhecido neste repositorio (19/19 hoje), nao uma quebra atual.
        4. `not queue_recovery["healthy"]` (Missao 47) - fila com job
           travado ou em inanicao pendente de recuperacao.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.diagnostics = DiagnosticsService(db)
        self.alerts = AlertService(db)
        self.recovery = RecoveryService(db)
        self.resources = ResourceManagerService(db)
        self.dependency_audit = DependencyAuditService()

    def _blocking_issues(
        self,
        diagnostics: dict[str, Any],
        active_alerts: list[dict[str, Any]],
        dependency_audit: dict[str, Any],
        queue_recovery: dict[str, Any],
    ) -> list[str]:
        issues: list[str] = []

        if diagnostics["status"] != STATUS_OK:
            issues.append(
                f"Diagnosticos com status '{diagnostics['status']}' "
                "(nem todos os checks de database/queue/cache/config/disk estao 'ok')."
            )

        if active_alerts:
            names = ", ".join(sorted({a["check_name"] for a in active_alerts}))
            issues.append(
                f"{len(active_alerts)} alerta(s) ativo(s) nao resolvido(s): {names}."
            )

        if dependency_audit["missing_count"] > 0:
            issues.append(
                f"{dependency_audit['missing_count']} dependencia(s) declarada(s) "
                "em requirements.txt ausente(s) do ambiente instalado."
            )
        if dependency_audit["version_mismatch_count"] > 0:
            issues.append(
                f"{dependency_audit['version_mismatch_count']} dependencia(s) com "
                "versao instalada diferente da versao fixada em requirements.txt."
            )

        if not queue_recovery["healthy"]:
            issues.append(
                "Fila de jobs nao saudavel: ha job(s) travado(s) e/ou em inanicao "
                "pendente(s) de recuperacao (RecoveryService)."
            )

        return issues

    def certify(self) -> dict[str, Any]:
        """Roda a certificacao Platinum agora e retorna o snapshot completo.
        Leitura pura - ver docstring da classe."""

        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)

        diagnostics = self.diagnostics.run_full_diagnostics()
        active_alerts = self.alerts.active_alerts()
        dependency_audit = self.dependency_audit.audit()
        queue_recovery = self.recovery.recovery_report()
        resource_usage = self.resources.disk_usage_report()

        blocking_issues = self._blocking_issues(
            diagnostics, active_alerts, dependency_audit, queue_recovery
        )

        strict_mode = self.settings.certification_platinum_require_clean_diagnostics
        platinum_certified = bool(strict_mode and not blocking_issues)

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "strict_mode": strict_mode,
            "config_validation_issues": config_validation_issues,
            "diagnostics_status": diagnostics["status"],
            "diagnostics_summary": diagnostics["summary"],
            "active_alerts_count": len(active_alerts),
            "active_alerts": active_alerts,
            "dependency_audit_summary": {
                "total_declared": dependency_audit["total_declared"],
                "pinned_count": dependency_audit["pinned_count"],
                "unpinned_count": dependency_audit["unpinned_count"],
                "missing_count": dependency_audit["missing_count"],
                "version_mismatch_count": dependency_audit["version_mismatch_count"],
                "issues": dependency_audit["issues"],
            },
            "queue_recovery": queue_recovery,
            "resource_usage": resource_usage,
            "missions_covered": list(MISSIONS_COVERED),
            "blocking_issues": blocking_issues,
            "platinum_certified": platinum_certified,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        """Renderiza o snapshot (ou roda certify() se nenhum for passado)
        como um relatorio Markdown legivel por humano."""

        report = snapshot if snapshot is not None else self.certify()

        lines: list[str] = []
        verdict = "PLATINUM CERTIFICADO" if report["platinum_certified"] else "NAO CERTIFICADO"
        lines.append(f"# Certificacao Platinum v1.3 - {verdict}")
        lines.append("")
        lines.append(f"- Gerado em: {report['generated_at']}")
        lines.append(f"- Ambiente: {report['environment']}")
        lines.append(f"- CONFIG_SCHEMA_VERSION: {report['config_schema_version']}")
        lines.append(f"- Modo estrito (gate ligado): {report['strict_mode']}")
        lines.append(f"- Status dos diagnosticos: {report['diagnostics_status']}")
        lines.append(f"- Alertas ativos: {report['active_alerts_count']}")
        lines.append("")

        lines.append("## Veredito")
        lines.append("")
        if report["blocking_issues"]:
            lines.append("Problema(s) bloqueante(s) encontrado(s):")
            lines.append("")
            for issue in report["blocking_issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("Nenhum problema bloqueante encontrado nos checks agregados.")
        lines.append("")

        lines.append("## Auditoria de dependencias (Missao 49)")
        lines.append("")
        dep = report["dependency_audit_summary"]
        lines.append(
            f"- Declaradas: {dep['total_declared']} | Fixadas: {dep['pinned_count']} | "
            f"Nao fixadas: {dep['unpinned_count']} | Ausentes: {dep['missing_count']} | "
            f"Divergentes: {dep['version_mismatch_count']}"
        )
        lines.append("")

        lines.append("## Recuperacao de fila (Missao 47)")
        lines.append("")
        qr = report["queue_recovery"]
        lines.append(
            f"- Saudavel: {qr['healthy']} | Recuperaveis agora: {qr['recoverable_now']} | "
            f"Requer acao externa: {qr['requires_external_action']}"
        )
        lines.append("")

        lines.append("## Missoes cobertas")
        lines.append("")
        for mission in report["missions_covered"]:
            lines.append(f"- Missao {mission['mission']} ({mission['name']}): {mission['summary']}")
        lines.append("")

        return "\n".join(lines)
