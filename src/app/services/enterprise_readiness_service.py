"""Missao 60 - Enterprise Readiness Certification.

Ultima missao da serie 51-60. Nao reimplementa nenhum dos nove motores
anteriores - agrega dois deles, que por sua vez ja agregam todos os
outros, evitando duplicacao de instanciacao (mesmo espirito "nunca
recalcula" repetido em todas as Missoes 57-59):

- `EvolutionDashboardService.current_snapshot()` (Missao 57) ja agrega
  Unified Certification (M53), Architecture Audit (M55) e Code Review
  (M56) - reusado aqui em vez de instanciar os tres motores de novo.
- `EvolutionDashboardService.mission_timeline()` / `timeline_health()`
  (Missao 57) - eixo informativo, nunca bloqueante.
- `ArchitectureStressTestService.stress_report()` (Missao 59).
- `TechDebtManagerService.debt_report()` (Missao 58) - eixo informativo,
  nunca bloqueante (mesma natureza ja documentada na propria Missao 58:
  e uma ferramenta de gestao de backlog, nao um veredito de certificacao).

Acrescenta uma dimensao nova, `mission_test_coverage`: para cada numero de
missao detectado na timeline real do git (Missao 57), confirma que existe
pelo menos um arquivo `test_m<N>_*.py` em `src/app/tests/` no disco - ou
seja, nao so "a missao existe no historico", mas "a missao tem suite
dedicada no repositorio hoje". Esta e a unica logica de calculo nova desta
missao; todo o resto e composicao pura dos motores ja existentes.

IMPORTANTE - leitura obrigatoria antes de usar este servico em qualquer
relatorio: o campo `enterprise_ready: bool` devolvido aqui e um veredito de
qualidade de engenharia INTERNO e ADICIONAL, criado por esta missao em
cima da v1.1 ja certificada. Ele NAO e, e nunca deve ser lido como, a
certificacao oficial da Fase Omega definida no `CLAUDE.md` do projeto
(que exige O01-O10 + tag `v1.1.0` no remoto - satisfeita separadamente,
antes desta serie de Missoes 51-60 comecar). Esta distincao e repetida no
`render_markdown()` abaixo e no relatorio desta missao, para que nenhum
leitor confunda os dois vereditos.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import project_root
from app.services.architecture_stress_test_service import ArchitectureStressTestService
from app.services.evolution_dashboard_service import EvolutionDashboardService
from app.services.tech_debt_manager_service import TechDebtManagerService

UTC = timezone.utc


class EnterpriseReadinessService:
    """Missao 60. Depende de `db` porque `EvolutionDashboardService`
    depende (transitivamente, via `UnifiedCertificationEngine` - mesmo
    motivo documentado na propria Missao 57). `ArchitectureStressTestService`
    e `TechDebtManagerService` nao precisam de banco, instanciados aqui sem
    `db`, mesmo padrao das Missoes 58/59."""

    def __init__(
        self,
        db: Session,
        evolution_dashboard: EvolutionDashboardService | None = None,
        stress_test: ArchitectureStressTestService | None = None,
        tech_debt_manager: TechDebtManagerService | None = None,
    ) -> None:
        self.db = db
        self.evolution_dashboard = evolution_dashboard or EvolutionDashboardService(db)
        self.stress_test = stress_test or ArchitectureStressTestService()
        self.tech_debt_manager = tech_debt_manager or TechDebtManagerService()

    def mission_test_coverage(
        self, timeline: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Eixo bloqueante novo desta missao: cada missao detectada na
        timeline real do git (Missao 57) precisa ter pelo menos um arquivo
        de suite dedicada em `src/app/tests/test_m<N>_*.py` no disco -
        prova que a missao nao so foi commitada, mas tem teste proprio
        hoje. Nunca finge cobertura: uma missao sem nenhum arquivo
        correspondente entra em `missions_without_dedicated_suite`."""
        timeline = (
            timeline if timeline is not None else self.evolution_dashboard.mission_timeline()
        )
        tests_dir = project_root() / "src" / "app" / "tests"

        covered: set[int] = set()
        missing: set[int] = set()
        for entry in timeline:
            number = entry["mission_number"]
            has_suite = any(tests_dir.glob(f"test_m{number}_*.py"))
            if has_suite:
                covered.add(number)
            else:
                missing.add(number)

        return {
            "total_missions_checked": len(timeline),
            "missions_with_dedicated_suite": sorted(covered),
            "missions_without_dedicated_suite": sorted(missing),
            "complete": len(missing) == 0,
        }

    def readiness_report(self) -> dict[str, Any]:
        """Leitura pura. Cinco eixos bloqueantes (todos precisam ser
        verdadeiros para `enterprise_ready=True`) mais contexto
        informativo que nunca bloqueia o veredito."""

        snapshot = self.evolution_dashboard.current_snapshot()
        stress = self.stress_test.stress_report()
        timeline = self.evolution_dashboard.mission_timeline()
        test_coverage = self.mission_test_coverage(timeline)
        timeline_health = self.evolution_dashboard.timeline_health(timeline)
        debt_report = self.tech_debt_manager.debt_report()

        blocking_axes = {
            "unified_certified": bool(snapshot["unified_certified"]),
            "architecture_clean": bool(snapshot["architecture_clean"]),
            "code_review_clean": bool(snapshot["code_review_clean"]),
            "stress_clean": bool(stress["clean"]),
            "mission_test_coverage_complete": bool(test_coverage["complete"]),
        }
        enterprise_ready = all(blocking_axes.values())

        return {
            "generated_at": datetime.now(UTC),
            "enterprise_ready": enterprise_ready,
            "blocking_axes": blocking_axes,
            "current_snapshot": snapshot,
            "stress_test": stress,
            "mission_test_coverage": test_coverage,
            "timeline_health": timeline_health,
            "tech_debt_summary": debt_report["summary"],
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.readiness_report()
        axes = report["blocking_axes"]
        verdict = (
            "ENTERPRISE READY" if report["enterprise_ready"] else "NAO PRONTO PARA ENTERPRISE"
        )

        lines: list[str] = [
            f"# Certificacao de Prontidao Enterprise (Missao 60) - {verdict}",
            "",
            f"- Gerado em: {report['generated_at']}",
            "",
            "## Eixos bloqueantes",
            "",
        ]
        for name, value in axes.items():
            marker = "OK" if value else "FALHOU"
            lines.append(f"- `{name}`: {marker}")

        coverage = report["mission_test_coverage"]
        lines.append("")
        lines.append(
            "- Cobertura de suite dedicada por missao: "
            f"{len(coverage['missions_with_dedicated_suite'])}/"
            f"{coverage['total_missions_checked']}"
        )
        if coverage["missions_without_dedicated_suite"]:
            lines.append(
                "- Missoes SEM suite dedicada: "
                f"{coverage['missions_without_dedicated_suite']}"
            )

        health = report["timeline_health"]
        lines.append("")
        lines.append("## Contexto informativo (nunca bloqueante)")
        lines.append("")
        lines.append(f"- Missoes detectadas no historico: {health['total_missions_detected']}")
        if health["missing_mission_numbers"]:
            lines.append(
                f"- Numeros ausentes na sequencia: {health['missing_mission_numbers']}"
            )
        if health["duplicate_mission_numbers"]:
            lines.append(f"- Numeros duplicados: {health['duplicate_mission_numbers']}")

        debt_summary = report["tech_debt_summary"]
        lines.append(
            f"- Divida tecnica conhecida: {debt_summary['total_debt_items']} itens em "
            f"{debt_summary['files_with_debt']} arquivo(s) "
            f"(pontuacao total {debt_summary['total_priority_score']})"
        )

        lines.append("")
        lines.append(
            "**IMPORTANTE**: este veredito e um agregador interno de qualidade de "
            "engenharia (Missao 60), adicional sobre a v1.1 ja certificada. NAO "
            "substitui nem redeclara a certificacao oficial da Fase Omega "
            "(O01-O10 + tag `v1.1.0` no remoto), satisfeita separadamente antes "
            "desta serie de missoes comecar."
        )

        return "\n".join(lines)
