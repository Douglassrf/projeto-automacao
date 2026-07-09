"""Missao 130 - Strategic Evolution Council (Fase v2.1).

Objetivo (BRIEFING_FASE_V2_1_MISSOES_122_131.md): "Criar um conselho
permanente de evolucao." Integrar: Arquitetura, QA, Seguranca,
Performance, Operacao, Documentacao. Criterio: "Toda grande evolucao
recebe parecer multidisciplinar."

Seis dominios, seis fontes reais, nenhuma reimplementada (regra 7 do
CLAUDE.md):

1. Arquitetura -> `ContinuousArchitectureScoringService.score_report()`
   (Missao 127) - indice de 5 eixos ja calculado ao vivo.
2. QA -> `CodeReviewService.review_repository()` (Missao 56) - revisao
   automatica via AST.
3. Seguranca -> `DependencyAuditService.audit()` (Missao 49), com a
   MESMA politica continua/lenientepara `unpinned_count` ja usada pelo
   Observatorio (Missao 124) - NAO a politica mais estrita do gate de
   release (Missao 126). Ver justificativa no docstring de
   `security_opinion()`.
4. Performance -> `ArchitectureStressTestService.stress_report()`
   (Missao 59).
5. Operacao -> `RecoveryService.recovery_report()` (Missao 47, que por
   sua vez reusa `QueueService.health_report()` da Missao 42).
6. Documentacao -> `DocumentationService.live_snapshot()` (Missao 48) -
   mesmos campos (`routes.failed`, `settings_issues`) ja usados pelo
   gate de release (Missao 126).

HEURISTICA EXPLICITA (regra 7 - este e literalmente o exemplo citado
no `CLAUDE.md`: "onde o julgamento for inerentemente qualitativo (ex.:
'parecer do conselho'), documentar explicitamente como heuristica, nao
como fato calculado"): o PARECER agregado do conselho
(`favoravel` / `favoravel_com_restricoes` / `desfavoravel`) e
calculado por uma contagem simples e documentada de quantos dos 6
dominios estao com `healthy=False` agora (0 -> favoravel; 1-2 ->
favoravel_com_restricoes; 3+ -> desfavoravel). Nao existe, em nenhuma
missao anterior, um limiar oficial para isso - e um corte de
legibilidade deliberado, nunca apresentado como fato calculado. Cada
PARECER POR DOMINIO individual, em contraste, e sempre um sinal real e
auditavel (booleano + numero + relatorio completo de uma missao
anterior) - nunca decorativo.

`change_description` (parametro opcional de `council_review()`) e
apenas um ROTULO de registro para o parecer - nao e analisado nem
interpretado (nenhuma missao anterior tem motor de NLP/LLM local, e a
regra 6 do CLAUDE.md proibe chamar uma API de IA paga so para isso). O
parecer e sempre calculado contra o estado AO VIVO real do
repositorio/servicos no momento da chamada, independente do texto
informado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.architecture_scoring_service import ContinuousArchitectureScoringService
from app.services.architecture_stress_test_service import ArchitectureStressTestService
from app.services.code_review_service import CodeReviewService
from app.services.dependency_audit_service import DependencyAuditService
from app.services.documentation_service import DocumentationService
from app.services.recovery_service import RecoveryService

UTC = timezone.utc

_DOMAIN_NAMES = ("arquitetura", "qa", "seguranca", "performance", "operacao", "documentacao")

_RECOMMENDATION_LABELS = {
    "favoravel": "FAVORAVEL",
    "favoravel_com_restricoes": "FAVORAVEL COM RESTRICOES",
    "desfavoravel": "DESFAVORAVEL",
}


def _recommendation(concern_count: int) -> str:
    """HEURISTICA EXPLICITA (regra 7) - ver docstring do modulo. Corte
    de legibilidade por contagem de dominios com preocupacao, nao um
    fato calculado."""
    if concern_count == 0:
        return "favoravel"
    if concern_count <= 2:
        return "favoravel_com_restricoes"
    return "desfavoravel"


class StrategicEvolutionCouncilService:
    """Missao 130. Depende de `db` porque `RecoveryService` (Missao 47)
    precisa de banco - mesmo motivo ja documentado na Missao 124, que
    tambem usa `RecoveryService`. As demais cinco dependencias
    (`ContinuousArchitectureScoringService`/127, `CodeReviewService`/56,
    `DependencyAuditService`/49, `ArchitectureStressTestService`/59,
    `DocumentationService`/48) nao precisam de banco."""

    def __init__(
        self,
        db: Session,
        architecture_scoring: ContinuousArchitectureScoringService | None = None,
        code_review: CodeReviewService | None = None,
        dependency_audit: DependencyAuditService | None = None,
        stress_test: ArchitectureStressTestService | None = None,
        recovery_service: RecoveryService | None = None,
        documentation: DocumentationService | None = None,
    ) -> None:
        self.db = db
        self.architecture_scoring = architecture_scoring or ContinuousArchitectureScoringService()
        self.code_review = code_review or CodeReviewService()
        self.dependency_audit = dependency_audit or DependencyAuditService()
        self.stress_test = stress_test or ArchitectureStressTestService()
        self.recovery_service = recovery_service or RecoveryService(db)
        self.documentation = documentation or DocumentationService()

    # --- seis pareceres de dominio, cada um chamavel isoladamente -----------

    def architecture_opinion(self) -> dict[str, Any]:
        """Arquitetura: reuso direto de
        ContinuousArchitectureScoringService.score_report() (Missao 127)."""
        report = self.architecture_scoring.score_report()
        healthy = report["overall_classification"] == "healthy"
        return {
            "domain": "arquitetura",
            "healthy": healthy,
            "signal": "overall_score (Missao 127)",
            "value": report["overall_score"],
            "detail": (
                f"classificacao={report['overall_classification']}, "
                f"dimensoes em atencao={report['attention_dimensions']}"
            ),
            "raw": report,
        }

    def qa_opinion(self) -> dict[str, Any]:
        """QA: reuso direto de CodeReviewService.review_repository()
        (Missao 56)."""
        review = self.code_review.review_repository()
        return {
            "domain": "qa",
            "healthy": review["clean"],
            "signal": "total_blocking_findings (Missao 56)",
            "value": review["total_blocking_findings"],
            "detail": (
                f"{review['files_with_findings']}/{review['total_files_scanned']} "
                "arquivo(s) com algum achado"
            ),
            "raw": review,
        }

    def security_opinion(self) -> dict[str, Any]:
        """Seguranca: reuso de DependencyAuditService.audit() (Missao
        49), com a politica continua/leniente da Missao 124 (nao a
        estrita da Missao 126). Justificativa: este conselho da um
        PARECER consultivo sobre evoluir a plataforma, nao um gate de
        release executado uma vez por release - usar a politica estrita
        tornaria este dominio permanentemente "com preocupacao" por um
        padrao do projeto ja classificado como aceitavel (dependencias
        sem pin por desenho, ver Missao 49/124). `unpinned_count`
        continua visivel em `raw`, so nao deriva o `healthy` aqui."""
        audit = self.dependency_audit.audit()
        healthy = audit["missing_count"] == 0 and audit["version_mismatch_count"] == 0
        return {
            "domain": "seguranca",
            "healthy": healthy,
            "signal": "missing_count + version_mismatch_count (Missao 49, politica da Missao 124)",
            "value": audit["missing_count"] + audit["version_mismatch_count"],
            "detail": (
                f"{audit['missing_count']} ausente(s), "
                f"{audit['version_mismatch_count']} com versao divergente, "
                f"{audit['unpinned_count']} sem pin (nao bloqueante aqui)"
            ),
            "raw": audit,
        }

    def performance_opinion(self) -> dict[str, Any]:
        """Performance: reuso direto de
        ArchitectureStressTestService.stress_report() (Missao 59)."""
        report = self.stress_test.stress_report()
        return {
            "domain": "performance",
            "healthy": report["clean"],
            "signal": "stress_report.clean (Missao 59)",
            "value": report["clean"],
            "detail": "teste de estresse de arquitetura (latencia/falhas sob carga + isolamento de container)",
            "raw": report,
        }

    def operacao_opinion(self) -> dict[str, Any]:
        """Operacao: reuso direto de RecoveryService.recovery_report()
        (Missao 47), que por sua vez reusa QueueService.health_report()
        (Missao 42)."""
        report = self.recovery_service.recovery_report()
        return {
            "domain": "operacao",
            "healthy": report["healthy"],
            "signal": "recovery_report.warnings (Missao 47)",
            "value": len(report["warnings"]),
            "detail": f"{len(report['warnings'])} aviso(s) operacional(is) ativo(s)",
            "raw": report,
        }

    def documentacao_opinion(self) -> dict[str, Any]:
        """Documentacao: reuso direto de
        DocumentationService.live_snapshot() (Missao 48) - mesmos
        campos usados pelo gate de release (Missao 126)."""
        snapshot = self.documentation.live_snapshot()
        routes = snapshot["routes"]
        healthy = routes["failed"] == 0 and len(snapshot["settings_issues"]) == 0
        return {
            "domain": "documentacao",
            "healthy": healthy,
            "signal": "routes.failed + settings_issues (Missao 48)",
            "value": routes["failed"] + len(snapshot["settings_issues"]),
            "detail": (
                f"{routes['failed']} rota(s) falharam ao carregar, "
                f"{len(snapshot['settings_issues'])} problema(s) de configuracao"
            ),
            "raw": snapshot,
        }

    # --- agregacao: parecer multidisciplinar ---------------------------------

    def council_review(self, change_description: str | None = None) -> dict[str, Any]:
        """Parecer multidisciplinar do conselho. Ver docstring do modulo
        sobre `change_description` (rotulo, nao analisado) e sobre a
        heuristica de `recommendation`."""
        opinions: dict[str, dict[str, Any]] = {
            "arquitetura": self.architecture_opinion(),
            "qa": self.qa_opinion(),
            "seguranca": self.security_opinion(),
            "performance": self.performance_opinion(),
            "operacao": self.operacao_opinion(),
            "documentacao": self.documentacao_opinion(),
        }

        concern_domains = sorted(name for name in _DOMAIN_NAMES if opinions[name]["healthy"] is False)
        supportive_domains = sorted(name for name in _DOMAIN_NAMES if opinions[name]["healthy"] is True)
        recommendation = _recommendation(len(concern_domains))

        return {
            "generated_at": datetime.now(UTC),
            "change_description": change_description,
            "recommendation": recommendation,
            "concern_domains": concern_domains,
            "supportive_domains": supportive_domains,
            "opinions": opinions,
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.council_review()
        opinions = report["opinions"]

        lines: list[str] = [
            "# Conselho Estrategico de Evolucao (Missao 130)",
            "",
            f"- Gerado em: {report['generated_at']}",
        ]
        if report["change_description"]:
            lines.append(f"- Evolucao em avaliacao: {report['change_description']}")
        lines.append(f"- Parecer: **{_RECOMMENDATION_LABELS[report['recommendation']]}**")
        lines.append("")
        lines.append("## Pareceres por dominio")
        lines.append("")

        for name in _DOMAIN_NAMES:
            data = opinions[name]
            marker = "OK" if data["healthy"] else "PREOCUPACAO"
            lines.append(f"- `{name}`: {marker} - {data['signal']} ({data['detail']})")

        lines.append("")
        if report["concern_domains"]:
            lines.append(f"## Dominios com preocupacao: {report['concern_domains']}")
            lines.append("")

        lines.append(
            "**IMPORTANTE**: o PARECER (favoravel/favoravel_com_restricoes/"
            "desfavoravel) e uma sintese HEURISTICA por contagem de dominios "
            "com preocupacao - julgamento qualitativo, documentado como tal "
            "(regra 7 do CLAUDE.md), nunca um fato calculado. Cada parecer "
            "por dominio, em contraste, reporta um sinal real e auditavel de "
            "uma missao anterior - nenhum numero decorativo."
        )

        return "\n".join(lines)
