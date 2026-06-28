"""Missao 128 - Autonomous Optimization Planner (Fase v2.1).

Setima missao da Fase v2.1. Objetivo literal do briefing: "Planejar
automaticamente melhorias." Produzir, para cada melhoria sugerida:
Backlog tecnico, Priorizacao, Ganho esperado, Impacto, Complexidade.
Criterio: "Melhorias sugeridas continuamente."

Esta missao nao reimplementa deteccao nem priorizacao - ela cruza dois
motores ja existentes para transformar uma lista de divida tecnica num
plano de otimizacao com 5 campos por item, todos reais (regra 7 do
CLAUDE.md - nada decorativo):

1. Backlog tecnico -> reuso direto de
   `TechDebtManagerService.debt_report()["backlog"]` (Missao 58) - a
   lista completa de achados informativos (`long_function`,
   `todo_marker`, `missing_docstring`), sem recalcular nada.

2. Priorizacao -> `priority_score` de cada item, ja calculado pela
   Missao 58 (peso da regra x idade real em dias via git) - reusado
   tal como esta; `priority_rank` aqui e so a posicao na lista ja
   ordenada (a Missao 58 e quem ordena, esta missao nao reordena).

3. Impacto -> cruzamento real com
   `ContinuousArchitectureScoringService.score_report()` (Missao 127):
   cada regra de divida afeta uma dimensao especifica da arquitetura
   (`_RULE_TO_DIMENSION` - `long_function` afeta `complexity`;
   `todo_marker`/`missing_docstring` afetam `maintainability`, ambos
   porque sao os mesmos dados que alimentam aquelas formulas na
   Missao 127). Um item cuja dimensao esta em
   `score_report()["attention_dimensions"]` (calculado ao vivo, nao
   fixo) recebe impacto "alto"; senao, "moderado".

4. Ganho esperado -> calculado a partir da MESMA formula que a
   Missao 127 usa para a dimensao afetada (nunca um numero arbitrario):
   - `complexity_score()` = (1 - long_function_count/total_files) * 100,
     linear em `long_function_count` - resolver uma ocorrencia de
     `long_function` ganha exatamente `100/total_files_scanned` pontos
     nessa dimensao, sempre.
   - `maintainability_score()` = (1 - files_with_debt/total_files) * 100,
     conta ARQUIVOS, nao itens - um item de `todo_marker`/
     `missing_docstring` so move essa dimensao se for o ULTIMO item de
     divida do seu arquivo no backlog atual (verificado contando quantos
     itens do backlog compartilham o mesmo `file`); quando nao e' o
     ultimo, o ganho esperado nessa dimensao e 0.0 (o item ainda reduz
     `total_priority_score` da Missao 58, que e reportado separadamente,
     mas nao move a pontuacao de arquitetura por si so).

5. Complexidade (esforco de implementacao) -> **HEURISTICA EXPLICITA**
   (regra 7): nao existe, em nenhuma missao anterior, um sinal real de
   "esforco de desenvolvedor para corrigir X" - seria necessario rodar
   o trabalho de fato para medir isso. Usa um mapeamento fixo e
   documentado por tipo de regra (`_EFFORT_TIER`): `long_function` =
   "alto" (pode exigir redesenhar a funcao), `todo_marker` = "medio"
   (depende do que o TODO descreve, mas geralmente contido a um ponto),
   `missing_docstring` = "baixo" (so escrever a docstring). Rotulado
   como heuristica no docstring e no relatorio - nunca apresentado como
   fato medido.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.architecture_scoring_service import ContinuousArchitectureScoringService
from app.services.tech_debt_manager_service import TechDebtManagerService

UTC = timezone.utc

# Qual dimensao da Missao 127 cada regra de divida tecnica (Missao 56/58)
# afeta - ver item 3 do docstring do modulo.
_RULE_TO_DIMENSION: dict[str, str] = {
    "long_function": "complexity",
    "todo_marker": "maintainability",
    "missing_docstring": "maintainability",
}

# Heuristica explicita (regra 7) - ver item 5 do docstring do modulo.
_EFFORT_TIER: dict[str, str] = {
    "long_function": "alto",
    "todo_marker": "medio",
    "missing_docstring": "baixo",
}


class AutonomousOptimizationPlannerService:
    """Missao 128. Sem `db` no construtor - as duas dependencias
    (`TechDebtManagerService`/Missao 58 e
    `ContinuousArchitectureScoringService`/Missao 127) tambem nao
    dependem de banco, mesmo motivo documentado nas Missoes 55/56/58/59
    /127."""

    def __init__(
        self,
        tech_debt_manager: TechDebtManagerService | None = None,
        architecture_scoring: ContinuousArchitectureScoringService | None = None,
    ) -> None:
        self.tech_debt_manager = tech_debt_manager or TechDebtManagerService()
        self.architecture_scoring = architecture_scoring or ContinuousArchitectureScoringService()

    def optimization_plan(self) -> dict[str, Any]:
        debt_report = self.tech_debt_manager.debt_report()
        score_report = self.architecture_scoring.score_report()

        backlog = debt_report["backlog"]
        attention_dimensions = set(score_report["attention_dimensions"])
        total_files_scanned = score_report["dimensions"]["complexity"]["raw"]["total_files_scanned"]

        file_item_counts: dict[str, int] = {}
        for item in backlog:
            file_item_counts[item["file"]] = file_item_counts.get(item["file"], 0) + 1

        recommendations: list[dict[str, Any]] = []
        for rank, item in enumerate(backlog, start=1):
            dimension = _RULE_TO_DIMENSION.get(item["rule"])
            expected_gain_points = 0.0
            if total_files_scanned:
                if dimension == "complexity":
                    expected_gain_points = round(100.0 / total_files_scanned, 2)
                elif dimension == "maintainability" and file_item_counts.get(item["file"]) == 1:
                    expected_gain_points = round(100.0 / total_files_scanned, 2)

            impact = "alto" if dimension in attention_dimensions else "moderado"

            recommendations.append(
                {
                    "priority_rank": rank,
                    "file": item["file"],
                    "line": item["line"],
                    "rule": item["rule"],
                    "detail": item["detail"],
                    "priority_score": item["priority_score"],
                    "affected_dimension": dimension,
                    "impact": impact,
                    "expected_gain_points": expected_gain_points,
                    "estimated_effort": _EFFORT_TIER.get(item["rule"], "desconhecido"),
                }
            )

        return {
            "generated_at": datetime.now(UTC),
            "total_recommendations": len(recommendations),
            "high_impact_count": sum(1 for r in recommendations if r["impact"] == "alto"),
            "total_expected_gain_points": round(
                sum(r["expected_gain_points"] for r in recommendations), 2
            ),
            "source_total_priority_score": debt_report["summary"]["total_priority_score"],
            "recommendations": recommendations,
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.optimization_plan()

        lines: list[str] = [
            "# Planejador Autonomo de Otimizacao (Missao 128)",
            "",
            f"- Gerado em: {report['generated_at']}",
            f"- Melhorias sugeridas: {report['total_recommendations']}",
            f"- De alto impacto (dimensao em atencao na Missao 127): {report['high_impact_count']}",
            f"- Ganho esperado total estimado: {report['total_expected_gain_points']} pontos (somados entre dimensoes, informativo)",
            f"- Pontuacao de prioridade total (Missao 58): {report['source_total_priority_score']}",
            "",
            "## Top 10 recomendacoes (por prioridade)",
            "",
        ]

        for rec in report["recommendations"][:10]:
            lines.append(
                f"- #{rec['priority_rank']} [{rec['rule']}] {rec['file']}:{rec['line']} - "
                f"impacto {rec['impact']} em `{rec['affected_dimension']}`, "
                f"ganho esperado {rec['expected_gain_points']} pts, "
                f"esforco estimado {rec['estimated_effort']} - {rec['detail']}"
            )

        if not report["recommendations"]:
            lines.append("(nenhuma melhoria pendente no backlog atual)")

        lines.append("")
        lines.append(
            "**IMPORTANTE**: `estimated_effort` e uma heuristica explicita (mapeamento "
            "fixo por tipo de regra, sem nenhuma medicao real de esforco de "
            "desenvolvedor - nao existe esse sinal no codebase). `impact` e "
            "`expected_gain_points` SAO calculados a partir do estado ao vivo da "
            "Missao 127 (Continuous Architecture Scoring) e da Missao 58 (Tech Debt "
            "Manager) - ver docstring do modulo para a formula exata de cada um."
        )

        return "\n".join(lines)
