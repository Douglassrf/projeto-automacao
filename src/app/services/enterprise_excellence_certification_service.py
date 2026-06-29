"""Missao 131 - Enterprise Excellence Certification (Fase v2.1, capstone).

Objetivo (BRIEFING_FASE_V2_1_MISSOES_122_131.md): "Executar a certificacao
maxima da plataforma", validando 12 dimensoes (Arquitetura, Governanca,
Seguranca, Performance, Observabilidade, Recuperacao, Qualidade,
Documentacao, Operacao, Evolucao, Conhecimento institucional,
Sustentabilidade tecnica) contra 5 criterios de aprovacao: zero
bloqueadores criticos, indicadores dentro das metas, evidencias
completas, aprovacao do conselho tecnico, plataforma pronta para
evolucao continua.

Este servico NAO reimplementa nenhum motor. E o agregador de topo da
Fase v2.1: consome diretamente os motores das Missoes 42, 47, 48, 49,
56, 57, 58, 122, 123, 124, 127 e o parecer multidisciplinar da Missao
130 (StrategicEvolutionCouncilService). Cada motor caro e chamado
exatamente UMA vez em todo o relatorio (ver nota de performance abaixo).

## Mapeamento das 12 dimensoes -> motor real reusado

  1. Arquitetura            -> ContinuousArchitectureScoringService.score_report()      (M127)
  2. Governanca              -> EvolutionDashboardService.current_snapshot()             (M57, unified_certified / M53)
  3. Seguranca                -> DependencyAuditService.audit()                          (M49, POLITICA ESTRITA - ver nota)
  4. Performance              -> EnterpriseQualityObservatoryService.quality_report()     (M124, sub-dimensao "performance", que por sua vez reusa stress_report() da M59)
  5. Observabilidade          -> EnterpriseQualityObservatoryService.quality_report()     (M124, relatorio completo)
  6. Recuperacao              -> RecoveryService.recovery_report()                       (M47, reusa QueueService.health_report()/M42)
  7. Qualidade                -> EvolutionDashboardService.current_snapshot()             (M57, code_review_clean / M56)
  8. Documentacao             -> DocumentationService.live_snapshot()                    (M48)
  9. Operacao                 -> QueueService.health_report()                            (M42)
 10. Evolucao                 -> ArchitectureEvolutionTimelineService.evolution_report()  (M123)
 11. Conhecimento institucional -> EngineeringMemoryCoreService.memory_report()          (M122)
 12. Sustentabilidade tecnica -> TechDebtManagerService.debt_report()                     (M58, informativo)

## Nota de performance (custo do teste de carga real, regra 7)

ArchitectureStressTestService.stress_report() (M59) e um teste de carga
real (TestClient(real_app), ~20 requisicoes HTTP reais, custo medido
isolado ~38-43s neste ambiente de dev - documentado desde as Missoes
59/60/124/130). Para nao pagar esse custo duas vezes no mesmo relatorio,
este servico chama EnterpriseQualityObservatoryService.quality_report()
exatamente UMA vez e reusa o mesmo resultado tanto para a dimensao
"Performance" quanto para a dimensao "Observabilidade" - nunca constroi
um ArchitectureStressTestService proprio.

## Politica de seguranca desta missao (estrita, diferente das M124/M130)

security_dimension() usa a politica ESTRITA: healthy exige
missing_count == 0 E version_mismatch_count == 0 E unpinned_count == 0.
Isto e deliberadamente mais rigoroso que a politica lenient das Missoes
124 e 130 (que ignoram unpinned_count) porque esta e uma certificacao
final/pontual, nao monitoramento continuo - o mesmo tipo de distincao
politica-estrita-vs-lenient ja documentado no modulo da Missao 130.

## Heuristicas explicitas (regra 7)

- `_dimension_target()`: cada dimensao "blocking" usa o `healthy` ja
  calculado pelo motor original (nenhum limiar novo e inventado aqui,
  exceto o limiar estrito de seguranca acima, que e uma escolha de
  politica documentada, nao um fato medido).
- Dimensoes 11 (conhecimento institucional) e 12 (sustentabilidade
  tecnica) sao informativas: reportam um valor real, mas nunca
  bloqueiam o veredito por si sos - mesma decisao ja tomada nas
  Missoes 58/60/124 para o eixo de divida tecnica.
- `aprovacao_conselho_tecnico`: heuristica explicita - o parecer do
  conselho (Missao 130) so BLOQUEIA esta certificacao quando a
  recomendacao e "desfavoravel". "favoravel" e "favoravel_com_restricoes"
  contam como aprovacao do conselho (com ou sem ressalvas), seguindo os
  proprios rotulos que a Missao 130 ja produz.
- `indicadores_dentro_das_metas`: varre as 12 dimensoes (nao so as 10
  bloqueantes) - escopo deliberadamente mais amplo que
  `zero_bloqueadores_criticos` (que olha somente as 10 bloqueantes).
  Na pratica, com os dados reais de hoje, os dois criterios produzem o
  mesmo booleano: `conhecimento_institucional` e
  `sustentabilidade_tecnica` sao sempre `healthy=None` (nenhuma meta
  real definida no codigo - inventar uma seria o numero decorativo que
  a regra 7 probe), e `None is False` e sempre falso, entao essas 2
  dimensoes nunca entram em `target_misses`. Os dois criterios
  continuam computos e nomeados separadamente porque o briefing os
  lista como 2 itens distintos do "Criterio de Aprovacao" - se uma
  missao futura definir uma meta real para um eixo hoje informativo,
  so o sweep mais amplo de `indicadores_dentro_das_metas` passaria a
  capturar isso, sem tocar em `zero_bloqueadores_criticos`.
- `change_description` nao existe aqui (esta nao e uma avaliacao de
  mudanca pontual como a M130, e sim uma fotografia do estado atual de
  toda a plataforma).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.architecture_evolution_timeline_service import (
    ArchitectureEvolutionTimelineService,
)
from app.services.architecture_stress_test_service import ArchitectureStressTestService
from app.services.architecture_scoring_service import ContinuousArchitectureScoringService
from app.services.dependency_audit_service import DependencyAuditService
from app.services.documentation_service import DocumentationService
from app.services.engineering_memory_core_service import EngineeringMemoryCoreService
from app.services.enterprise_quality_observatory_service import (
    EnterpriseQualityObservatoryService,
)
from app.services.evolution_dashboard_service import EvolutionDashboardService
from app.services.queue_service import QueueService
from app.services.recovery_service import RecoveryService
from app.services.strategic_evolution_council_service import (
    StrategicEvolutionCouncilService,
)
from app.services.tech_debt_manager_service import TechDebtManagerService

UTC = timezone.utc

_DIMENSION_NAMES = (
    "arquitetura",
    "governanca",
    "seguranca",
    "performance",
    "observabilidade",
    "recuperacao",
    "qualidade",
    "documentacao",
    "operacao",
    "evolucao",
    "conhecimento_institucional",
    "sustentabilidade_tecnica",
)

# Dimensoes que participam do gate "zero bloqueadores criticos". As duas
# de fora (conhecimento_institucional, sustentabilidade_tecnica) sao
# informativas por design - mesma decisao das Missoes 58/60/124.
_BLOCKING_DIMENSIONS = (
    "arquitetura",
    "governanca",
    "seguranca",
    "performance",
    "observabilidade",
    "recuperacao",
    "qualidade",
    "documentacao",
    "operacao",
    "evolucao",
)

_COUNCIL_BLOCKING_RECOMMENDATION = "desfavoravel"
"""Heuristica explicita (regra 7): so esta recomendacao do conselho
(Missao 130) bloqueia a certificacao. Ver docstring do modulo."""


class _SingleFlightStressTest:
    """Memoiza ArchitectureStressTestService.stress_report() para uma
    unica execucao por instancia.

    Tanto EnterpriseQualityObservatoryService.quality_report() (M124)
    quanto StrategicEvolutionCouncilService.council_review() (M130)
    chamam stress_report() (M59) internamente, cada um com sua propria
    instancia de ArchitectureStressTestService por padrao. stress_report()
    e um teste de carga REAL (~20 requisicoes HTTP via TestClient contra o
    app vivo, ~38-43s neste ambiente de dev - ver docstrings das Missoes
    59/124/130). certification_report() chama AMBOS os metodos acima, e
    sem este shim o teste de carga real dispararia DUAS vezes
    (~80s+, desperdicando o segundo load test). Este wrapper e injetado
    nas DUAS sub-instancias para garantir uma unica chamada real por
    relatorio - o dado retornado e sempre o output genuino do motor
    real, apenas computado uma vez e reusado (regra 7: nao e numero
    decorativo, e o mesmo motor real, sem redundancia evitavel)."""

    def __init__(self, engine: ArchitectureStressTestService) -> None:
        self._engine = engine
        self._cache: dict[str, Any] | None = None

    def stress_report(self) -> dict[str, Any]:
        if self._cache is None:
            self._cache = self._engine.stress_report()
        return self._cache


class EnterpriseExcellenceCertificationService:
    """Missao 131. Agregador de topo da Fase v2.1 - consome os motores
    das Missoes 42/47/48/49/56/57/58/122/123/124/127/130, nenhum
    reimplementado aqui."""

    def __init__(
        self,
        db: Session,
        evolution_dashboard: EvolutionDashboardService | None = None,
        architecture_scoring: ContinuousArchitectureScoringService | None = None,
        dependency_audit: DependencyAuditService | None = None,
        quality_observatory: EnterpriseQualityObservatoryService | None = None,
        recovery_service: RecoveryService | None = None,
        queue_service: QueueService | None = None,
        documentation: DocumentationService | None = None,
        evolution_timeline: ArchitectureEvolutionTimelineService | None = None,
        memory_core: EngineeringMemoryCoreService | None = None,
        tech_debt_manager: TechDebtManagerService | None = None,
        council: StrategicEvolutionCouncilService | None = None,
    ) -> None:
        self.db = db
        self.evolution_dashboard = evolution_dashboard or EvolutionDashboardService(db)
        self.architecture_scoring = architecture_scoring or ContinuousArchitectureScoringService()
        self.dependency_audit = dependency_audit or DependencyAuditService()
        # Shim de chamada-unica (ver _SingleFlightStressTest acima) -
        # so e usado para as instancias default que esta classe constroi
        # sozinha; quality_observatory/council explicitos (testes com
        # fakes) nunca sao tocados por isto.
        _shared_stress_test = _SingleFlightStressTest(ArchitectureStressTestService())
        self.quality_observatory = quality_observatory or EnterpriseQualityObservatoryService(
            db, stress_test=_shared_stress_test
        )
        self.recovery_service = recovery_service or RecoveryService(db)
        self.queue_service = queue_service or QueueService(db)
        self.documentation = documentation or DocumentationService()
        self.evolution_timeline = evolution_timeline or ArchitectureEvolutionTimelineService(db)
        self.memory_core = memory_core or EngineeringMemoryCoreService(db)
        self.tech_debt_manager = tech_debt_manager or TechDebtManagerService()
        self.council = council or StrategicEvolutionCouncilService(db, stress_test=_shared_stress_test)

    # --- as 12 dimensoes --------------------------------------------------

    def arquitetura_dimension(self) -> dict[str, Any]:
        score = self.architecture_scoring.score_report()
        return {
            "dimension": "arquitetura",
            "blocking": True,
            "healthy": score["overall_classification"] == "healthy",
            "signal": "overall_classification (ContinuousArchitectureScoringService, M127)",
            "value": score["overall_score"],
            "detail": f"score={score['overall_score']}, atencao em {score['attention_dimensions']}",
            "raw": score,
        }

    def governanca_dimension(self, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        """Reusa EvolutionDashboardService.current_snapshot() (M57) - a
        mesma chamada e compartilhada com qualidade_dimension() via
        all_dimensions(), nunca duas chamadas independentes."""
        snapshot = snapshot if snapshot is not None else self.evolution_dashboard.current_snapshot()
        return {
            "dimension": "governanca",
            "blocking": True,
            "healthy": bool(snapshot["unified_certified"]),
            "signal": "unified_certified (UnifiedCertificationEngine, M53, via EvolutionDashboardService/M57)",
            "value": snapshot["unified_certified"],
            "detail": f"platinum={snapshot['platinum_certified']}, gold={snapshot['gold_certified']}",
            "raw": snapshot,
        }

    def seguranca_dimension(self) -> dict[str, Any]:
        """Politica ESTRITA (diferente das Missoes 124/130 - ver docstring
        do modulo): healthy exige missing+mismatch+unpinned == 0."""
        audit = self.dependency_audit.audit()
        healthy = (
            audit["missing_count"] == 0
            and audit["version_mismatch_count"] == 0
            and audit["unpinned_count"] == 0
        )
        return {
            "dimension": "seguranca",
            "blocking": True,
            "healthy": healthy,
            "signal": "missing_count+version_mismatch_count+unpinned_count, politica ESTRITA (DependencyAuditService, M49)",
            "value": audit["missing_count"] + audit["version_mismatch_count"] + audit["unpinned_count"],
            "detail": (
                f"missing={audit['missing_count']}, mismatch={audit['version_mismatch_count']}, "
                f"unpinned={audit['unpinned_count']}"
            ),
            "raw": audit,
        }

    def performance_dimension(self, quality_report: dict[str, Any] | None = None) -> dict[str, Any]:
        """Reusa EnterpriseQualityObservatoryService.quality_report() (M124)
        - nunca chama ArchitectureStressTestService diretamente (ver nota
        de performance no docstring do modulo)."""
        quality_report = quality_report if quality_report is not None else self.quality_observatory.quality_report()
        perf = quality_report["monitored_dimensions"]["performance"]
        return {
            "dimension": "performance",
            "blocking": True,
            "healthy": bool(perf["healthy"]),
            "signal": "monitored_dimensions.performance (EnterpriseQualityObservatoryService, M124, reusa stress_report()/M59)",
            "value": perf["value"],
            "detail": f"stress_report.clean={perf['value']}",
            "raw": perf,
        }

    def observabilidade_dimension(self, quality_report: dict[str, Any] | None = None) -> dict[str, Any]:
        """A propria existencia de um observatorio continuo computavel e
        sem dimensoes em alerta E o sinal de observabilidade (M124)."""
        quality_report = quality_report if quality_report is not None else self.quality_observatory.quality_report()
        unhealthy = quality_report["unhealthy_dimensions"]
        return {
            "dimension": "observabilidade",
            "blocking": True,
            "healthy": len(unhealthy) == 0,
            "signal": "unhealthy_dimensions (EnterpriseQualityObservatoryService, M124)",
            "value": len(unhealthy),
            "detail": f"dimensoes em alerta: {unhealthy}" if unhealthy else "nenhuma dimensao em alerta",
            "raw": quality_report,
        }

    def recuperacao_dimension(self) -> dict[str, Any]:
        report = self.recovery_service.recovery_report()
        return {
            "dimension": "recuperacao",
            "blocking": True,
            "healthy": bool(report["healthy"]),
            "signal": "recovery_report.healthy (RecoveryService, M47)",
            "value": len(report["warnings"]),
            "detail": (
                f"recuperaveis agora={report['recoverable_now']}, "
                f"exigem acao externa={report['requires_external_action']}"
            ),
            "raw": report,
        }

    def qualidade_dimension(self, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        """Reusa EvolutionDashboardService.current_snapshot() (M57) - a
        mesma chamada e compartilhada com governanca_dimension() via
        all_dimensions(), nunca duas chamadas independentes."""
        snapshot = snapshot if snapshot is not None else self.evolution_dashboard.current_snapshot()
        return {
            "dimension": "qualidade",
            "blocking": True,
            "healthy": bool(snapshot["code_review_clean"]),
            "signal": "code_review_clean (CodeReviewService, M56, via EvolutionDashboardService/M57)",
            "value": snapshot["code_review_blocking_findings"],
            "detail": f"findings bloqueantes={snapshot['code_review_blocking_findings']}",
            "raw": snapshot,
        }

    def documentacao_dimension(self) -> dict[str, Any]:
        snapshot = self.documentation.live_snapshot()
        routes = snapshot["routes"]
        healthy = routes["failed"] == 0 and len(snapshot["settings_issues"]) == 0
        return {
            "dimension": "documentacao",
            "blocking": True,
            "healthy": healthy,
            "signal": "routes.failed + settings_issues (DocumentationService, M48)",
            "value": routes["failed"] + len(snapshot["settings_issues"]),
            "detail": f"rotas falhando={routes['failed']}, settings_issues={len(snapshot['settings_issues'])}",
            "raw": snapshot,
        }

    def operacao_dimension(self) -> dict[str, Any]:
        report = self.queue_service.health_report()
        return {
            "dimension": "operacao",
            "blocking": True,
            "healthy": bool(report["healthy"]),
            "signal": "health_report.healthy (QueueService, M42)",
            "value": len(report["warnings"]),
            "detail": f"avisos={report['warnings']}" if report["warnings"] else "sem avisos",
            "raw": report,
        }

    def evolucao_dimension(self) -> dict[str, Any]:
        report = self.evolution_timeline.evolution_report()
        gap_count = ArchitectureEvolutionTimelineService._gap_count(report)
        return {
            "dimension": "evolucao",
            "blocking": True,
            "healthy": gap_count == 0,
            "signal": "files_without_history (ArchitectureEvolutionTimelineService, M123)",
            "value": gap_count,
            "detail": f"arquivos sem historico rastreado={gap_count}",
            "raw": report,
        }

    def conhecimento_institucional_dimension(self) -> dict[str, Any]:
        """Informativo, nunca bloqueante - mesma semantica de
        sustentabilidade_tecnica_dimension() (healthy=None sempre). Nao
        existe no codigo um numero real de "missoes minimas" que defina
        memoria institucional suficiente - inventar um limiar aqui seria
        exatamente o tipo de numero decorativo que a regra 7 probe.
        `value`/`detail` continuam reais e uteis para leitura humana."""
        report = self.memory_core.memory_report()
        mission_count = len(report["mission_history"])
        return {
            "dimension": "conhecimento_institucional",
            "blocking": False,
            "healthy": None,
            "signal": "len(mission_history) (EngineeringMemoryCoreService, M122, informativo, nunca bloqueante)",
            "value": mission_count,
            "detail": (
                f"missoes registradas={mission_count}, decisoes arquiteturais="
                f"{len(report['architectural_decision_history'])}, incidentes="
                f"{len(report['incident_history'])}"
            ),
            "raw": report,
        }

    def sustentabilidade_tecnica_dimension(self) -> dict[str, Any]:
        """Informativo, nunca bloqueante - mesma decisao das Missoes
        58/60/124 para o eixo de divida tecnica."""
        report = self.tech_debt_manager.debt_report()
        summary = report["summary"]
        return {
            "dimension": "sustentabilidade_tecnica",
            "blocking": False,
            "healthy": None,
            "signal": "total_debt_items (TechDebtManagerService, M58, informativo, nunca bloqueante)",
            "value": summary["total_debt_items"],
            "detail": (
                f"itens={summary['total_debt_items']}, arquivos com divida="
                f"{summary['files_with_debt']}, pontuacao total={summary['total_priority_score']}"
            ),
            "raw": report,
        }

    # --- agregacao ----------------------------------------------------

    def all_dimensions(self) -> dict[str, dict[str, Any]]:
        """Cada motor caro/compartilhado e chamado exatamente uma vez:
        quality_report() (performance + observabilidade) e
        current_snapshot() (governanca + qualidade)."""
        quality_report = self.quality_observatory.quality_report()
        snapshot = self.evolution_dashboard.current_snapshot()
        return {
            "arquitetura": self.arquitetura_dimension(),
            "governanca": self.governanca_dimension(snapshot),
            "seguranca": self.seguranca_dimension(),
            "performance": self.performance_dimension(quality_report),
            "observabilidade": self.observabilidade_dimension(quality_report),
            "recuperacao": self.recuperacao_dimension(),
            "qualidade": self.qualidade_dimension(snapshot),
            "documentacao": self.documentacao_dimension(),
            "operacao": self.operacao_dimension(),
            "evolucao": self.evolucao_dimension(),
            "conhecimento_institucional": self.conhecimento_institucional_dimension(),
            "sustentabilidade_tecnica": self.sustentabilidade_tecnica_dimension(),
        }

    def certification_report(self) -> dict[str, Any]:
        dimensions = self.all_dimensions()
        council_review = self.council.council_review()

        blocking_failures = sorted(
            name for name in _BLOCKING_DIMENSIONS if dimensions[name]["healthy"] is False
        )
        zero_bloqueadores_criticos = len(blocking_failures) == 0

        target_misses = sorted(
            name for name in _DIMENSION_NAMES if dimensions[name]["healthy"] is False
        )
        indicadores_dentro_das_metas = len(target_misses) == 0

        evidencias_completas = len(dimensions) == len(_DIMENSION_NAMES) and all(
            "value" in d and "raw" in d and d["raw"] is not None for d in dimensions.values()
        ) and council_review is not None

        aprovacao_conselho_tecnico = council_review["recommendation"] != _COUNCIL_BLOCKING_RECOMMENDATION

        criteria = {
            "zero_bloqueadores_criticos": zero_bloqueadores_criticos,
            "indicadores_dentro_das_metas": indicadores_dentro_das_metas,
            "evidencias_completas": evidencias_completas,
            "aprovacao_conselho_tecnico": aprovacao_conselho_tecnico,
        }
        pronta_para_evolucao_continua = all(criteria.values())
        criteria["pronta_para_evolucao_continua"] = pronta_para_evolucao_continua

        certified = pronta_para_evolucao_continua

        return {
            "generated_at": datetime.now(UTC),
            "certified": certified,
            "criteria": criteria,
            "blocking_failures": blocking_failures,
            "target_misses": target_misses,
            "dimensions": dimensions,
            "council_review": council_review,
        }

    # --- relatorio textual ---------------------------------------------

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.certification_report()
        dims = report["dimensions"]
        criteria = report["criteria"]

        lines: list[str] = [
            "# Enterprise Excellence Certification (Missao 131)",
            "",
            f"- Gerado em: {report['generated_at']}",
            f"- Veredito: {'CERTIFICADA' if report['certified'] else 'NAO CERTIFICADA'}",
            "",
            "## Criterios de aprovacao",
            "",
        ]
        for name, value in criteria.items():
            marker = "OK" if value else "FALHA"
            lines.append(f"- [{marker}] {name}: {value}")

        lines.append("")
        lines.append("## Dimensoes (12)")
        lines.append("")
        for name in _DIMENSION_NAMES:
            data = dims[name]
            if data["healthy"] is None:
                marker = "INFO"
            elif data["healthy"]:
                marker = "OK"
            else:
                marker = "PREOCUPACAO"
            blocking_tag = "" if data["blocking"] else " (informativo)"
            lines.append(f"- [{marker}] {name}{blocking_tag}: {data['detail']}")

        if report["blocking_failures"]:
            lines.append("")
            lines.append(f"## Bloqueadores criticos: {report['blocking_failures']}")

        if report["target_misses"]:
            lines.append("")
            lines.append(f"## Indicadores fora da meta: {report['target_misses']}")

        lines.append("")
        lines.append("## Parecer do conselho tecnico (Missao 130)")
        lines.append(f"- recomendacao: {report['council_review']['recommendation']}")
        lines.append(f"- dominios em preocupacao: {report['council_review']['concern_domains']}")

        lines.append("")
        lines.append(
            "**Heuristica (regra 7):** o veredito 'certified' e a conjuncao de 4 "
            "criterios reais (zero bloqueadores, indicadores nas metas, evidencias "
            "completas, aprovacao do conselho). 'pronta_para_evolucao_continua' e "
            "esse mesmo AND, exposto como o 5o criterio do briefing - nao e um "
            "calculo independente. As dimensoes 'conhecimento_institucional' e "
            "'sustentabilidade_tecnica' sao informativas e nunca bloqueiam o "
            "veredito, mesma decisao ja tomada nas Missoes 58/60/124."
        )

        return "\n".join(lines)
