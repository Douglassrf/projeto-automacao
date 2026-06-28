"""Missao 127 - Continuous Architecture Scoring (Fase v2.1).

Sexta missao da Fase v2.1. Objetivo literal do briefing: "criar um indice
permanente da arquitetura", avaliando cinco eixos (Modularidade,
Acoplamento, Coesao, Complexidade, Manutenibilidade) com "pontuacao
atualizada continuamente" - ou seja, um SCORE recalculado a cada chamada
(estilo observatorio, como a Missao 124), nao um gate binario (estilo
Missao 126). Cada eixo produz um numero real em 0-100, nunca decorativo
(regra 7 do CLAUDE.md):

1. Modularidade -> reuso de `ArchitectureAuditService.audit()` (Missao 55):
   conta quantos dos 3 eixos bloqueantes (config_centralization,
   route_discovery, route_collisions) estao limpos agora. Score =
   (eixos limpos / 3) * 100.
2. Acoplamento -> reuso direto de
   `ArchitectureAuditService.audit_di_adoption()["adoption_rate"]`
   (Missao 55), que ja e um ratio 0.0-1.0: modulo de rota que usa o
   container de DI depende so da abstracao (`get_xxx_service`), nao da
   classe concreta - adesao mais alta = menos acoplamento direto entre
   rota e implementacao. Score = adoption_rate * 100.
3. Coesao -> NAO existe sinal pronto para isto em nenhuma missao
   anterior. Computado aqui via AST, ao vivo, contra `src/app/services/`
   (a camada que este proprio projeto construiu, missao a missao, com a
   convencao de "uma classe de Service por arquivo"): conta classes de
   topo por arquivo. Score = (arquivos com exatamente 1 classe de topo /
   total de arquivos) * 100. **Heuristica explicita** (regra 7): coesao
   de verdade e semantica (responsabilidades relacionadas agrupadas
   juntas); contagem de classes por arquivo so mede adesao estrutural a
   convencao 1-classe-por-arquivo que este repositorio ja adota - e um
   proxy real e calculado, nao uma medida completa de coesao.
4. Complexidade -> reuso de `CodeReviewService.review_repository()`
   (Missao 56), eixo informativo `long_function` (funcao com corpo >
   60 linhas, limiar ja documentado na Missao 56). Score = (1 -
   long_function_count / total_files_scanned) * 100, fixado em [0, 100].
5. Manutenibilidade -> reuso de `TechDebtManagerService.debt_report()`
   (Missao 58, que por sua vez reusa CodeReviewService) e de
   `total_files_scanned` (Missao 56, mesma chamada do eixo 4, sem
   recalcular). Score = (1 - files_with_debt / total_files_scanned) *
   100 - fracao de arquivos sem nenhum item de divida tecnica conhecido.

Classificacao "healthy"/"attention" por eixo usa um limiar heuristico
documentado (`_HEALTHY_SCORE_THRESHOLD`), nunca tratado como fato
calculado - apenas como corte de leitura humana sobre o numero real.

`overall_score()` e a media aritmetica simples dos 5 eixos - escolha
deliberada e documentada (nenhum peso oculto por eixo)."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import project_root
from app.services.architecture_audit_service import ArchitectureAuditService
from app.services.code_review_service import CodeReviewService
from app.services.tech_debt_manager_service import TechDebtManagerService

UTC = timezone.utc

_HEALTHY_SCORE_THRESHOLD = 70.0
_DIMENSION_NAMES = ("modularity", "coupling", "cohesion", "complexity", "maintainability")


def _services_dir() -> Path:
    return project_root() / "src" / "app" / "services"


def _classification(score: float) -> str:
    """Heuristica explicita (regra 7): >= 70 e um corte de leitura, nao um
    fato medido - documentado aqui e repetido no docstring do modulo."""
    return "healthy" if score >= _HEALTHY_SCORE_THRESHOLD else "attention"


class ContinuousArchitectureScoringService:
    """Missao 127. Sem `db` no construtor - nenhum dos 5 eixos depende de
    banco, so de codigo-fonte real (mesmo motivo documentado em
    `ArchitectureAuditService`/Missao 55, `CodeReviewService`/Missao 56 e
    `TechDebtManagerService`/Missao 58)."""

    def __init__(
        self,
        architecture_audit: ArchitectureAuditService | None = None,
        code_review: CodeReviewService | None = None,
        tech_debt_manager: TechDebtManagerService | None = None,
    ) -> None:
        self.architecture_audit = architecture_audit or ArchitectureAuditService()
        self.code_review = code_review or CodeReviewService()
        self.tech_debt_manager = tech_debt_manager or TechDebtManagerService()

    # --- cinco eixos, cada um chamavel isoladamente -------------------------

    def modularity_score(self) -> dict[str, Any]:
        audit = self.architecture_audit.audit()
        blocking_checks = (
            audit["config_centralization"]["clean"],
            audit["route_discovery"]["clean"],
            audit["route_collisions"]["clean"],
        )
        clean_count = sum(1 for ok in blocking_checks if ok)
        score = round((clean_count / len(blocking_checks)) * 100, 2)
        return {
            "score": score,
            "classification": _classification(score),
            "signal": "ArchitectureAuditService.audit() - eixos bloqueantes limpos",
            "detail": f"{clean_count}/{len(blocking_checks)} eixo(s) estrutural(is) limpo(s) agora",
            "raw": audit,
        }

    def coupling_score(self) -> dict[str, Any]:
        di_adoption = self.architecture_audit.audit_di_adoption()
        score = round(di_adoption["adoption_rate"] * 100, 2)
        return {
            "score": score,
            "classification": _classification(score),
            "signal": "ArchitectureAuditService.audit_di_adoption().adoption_rate",
            "detail": (
                f"{len(di_adoption['via_container'])}/{di_adoption['total_route_modules']} "
                "modulo(s) de rota desacoplados via container de DI"
            ),
            "raw": di_adoption,
        }

    def cohesion_score(self, services_dir: Path | None = None) -> dict[str, Any]:
        """Heuristica explicita - ver docstring do modulo, item 3.
        `services_dir` existe para permitir teste com uma pasta sintetica,
        sem tocar em `src/app/services/` real - mesmo padrao de
        `source: str | None` ja usado em `ArchitectureAuditService`
        (Missao 55)."""
        services_dir = services_dir if services_dir is not None else _services_dir()
        file_class_counts: dict[str, int] = {}
        for path in sorted(services_dir.glob("*.py")):
            if path.name == "__init__.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            top_level_classes = sum(1 for node in tree.body if isinstance(node, ast.ClassDef))
            file_class_counts[path.name] = top_level_classes

        total_files = len(file_class_counts)
        single_class_files = sum(1 for count in file_class_counts.values() if count == 1)
        score = round((single_class_files / total_files) * 100, 2) if total_files else 0.0
        off_convention = sorted(name for name, count in file_class_counts.items() if count != 1)

        return {
            "score": score,
            "classification": _classification(score),
            "signal": "services/*.py com exatamente 1 classe de topo (heuristica)",
            "detail": f"{single_class_files}/{total_files} arquivo(s) de servico seguem a convencao 1-classe-por-arquivo",
            "files_off_convention": off_convention,
            "raw": file_class_counts,
        }

    def complexity_score(self) -> dict[str, Any]:
        review = self.code_review.review_repository()
        total_files = review["total_files_scanned"]
        long_function_count = review["rule_counts"].get("long_function", 0)
        ratio_clean = 1.0 - (long_function_count / total_files) if total_files else 1.0
        score = round(max(0.0, min(1.0, ratio_clean)) * 100, 2)
        return {
            "score": score,
            "classification": _classification(score),
            "signal": "CodeReviewService.review_repository().rule_counts['long_function']",
            "detail": f"{long_function_count} funcao(oes) longa(s) (>60 linhas) entre {total_files} arquivo(s) varridos",
            "raw": review,
        }

    def maintainability_score(self) -> dict[str, Any]:
        debt = self.tech_debt_manager.debt_report()
        review = self.code_review.review_repository()
        total_files = review["total_files_scanned"]
        files_with_debt = debt["summary"]["files_with_debt"]
        ratio_clean = 1.0 - (files_with_debt / total_files) if total_files else 1.0
        score = round(max(0.0, min(1.0, ratio_clean)) * 100, 2)
        return {
            "score": score,
            "classification": _classification(score),
            "signal": "TechDebtManagerService.debt_report().summary.files_with_debt",
            "detail": f"{files_with_debt}/{total_files} arquivo(s) com algum item de divida tecnica conhecido",
            "raw": debt,
        }

    # --- agregacao -------------------------------------------------------------

    def score_report(self) -> dict[str, Any]:
        dimensions = {
            "modularity": self.modularity_score(),
            "coupling": self.coupling_score(),
            "cohesion": self.cohesion_score(),
            "complexity": self.complexity_score(),
            "maintainability": self.maintainability_score(),
        }
        overall_score = round(sum(dimensions[name]["score"] for name in _DIMENSION_NAMES) / len(_DIMENSION_NAMES), 2)
        attention_dimensions = sorted(
            name for name in _DIMENSION_NAMES if dimensions[name]["classification"] == "attention"
        )

        return {
            "generated_at": datetime.now(UTC),
            "overall_score": overall_score,
            "overall_classification": _classification(overall_score),
            "attention_dimensions": attention_dimensions,
            "dimensions": dimensions,
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.score_report()
        dimensions = report["dimensions"]

        lines: list[str] = [
            "# Pontuacao Continua de Arquitetura (Missao 127)",
            "",
            f"- Gerado em: {report['generated_at']}",
            f"- Pontuacao geral: **{report['overall_score']}/100** ({report['overall_classification']})",
            "",
            "## Eixos",
            "",
        ]
        for name in _DIMENSION_NAMES:
            data = dimensions[name]
            marker = "OK" if data["classification"] == "healthy" else "ATENCAO"
            lines.append(f"- `{name}`: {data['score']}/100 [{marker}] - {data['detail']}")

        if report["attention_dimensions"]:
            lines.append("")
            lines.append(f"## Eixos que pedem atencao: {report['attention_dimensions']}")

        lines.append("")
        lines.append(
            "**IMPORTANTE**: `cohesion_score()` e uma heuristica explicita (adesao "
            "estrutural a convencao 1-classe-por-arquivo em services/), nao uma medida "
            "semantica completa de coesao. O limiar de 70 para classificar um eixo como "
            "'healthy' tambem e heuristico (corte de leitura humana), nao um fato "
            "calculado - ver docstring do modulo."
        )

        return "\n".join(lines)
