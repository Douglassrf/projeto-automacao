"""Missao 129 - Engineering Digital Twin (Fase v2.1).

Objetivo (BRIEFING_FASE_V2_1_MISSOES_122_131.md): criar um "gemeo
digital" da arquitetura. Simular: Novos modulos, Refatoracoes,
Alteracoes, Crescimento, Migracoes. Criterio: "Mudancas avaliadas
virtualmente antes da implementacao."

Esta missao NAO toca em nenhum arquivo real - ela responde "se eu
fizer X, a pontuacao da Missao 127 mudaria para quanto?" sem aplicar
nada de fato.

Por que isso NAO e decorativo (regra 7 do CLAUDE.md): toda simulacao
parte do estado AO VIVO real de
`ContinuousArchitectureScoringService.score_report()` (Missao 127)
como linha de base, extrai os contadores brutos que alimentam cada
formula daquela missao (ja documentados la: clean_count/3 para
modularidade; via_container/total_route_modules para acoplamento;
single_class_files/total_files para coesao;
1-long_function/total_files para complexidade;
1-files_with_debt/total_files para manutenibilidade) e reaplica as
MESMAS formulas com um ou mais contadores trocados pelo valor
hipotetico do cenario. O numero de saida nunca e fixo: e sempre
baseline real + formula real (a mesma da Missao 127, reproduzida aqui
como funcao pura) + delta hipotetico explicito nos parametros do
cenario.

Cinco tipos de cenario (== os 5 itens "Simular" do briefing):

1. `novo_modulo` -> adicionar um arquivo de servico novo (afeta
   coesao) e, opcionalmente, um modulo de rota novo (afeta
   acoplamento, conforme ele use ou nao o container de DI).
2. `refatoracao` -> resolver K ocorrencias de `long_function`
   existentes hoje no backlog (afeta complexidade).
3. `correcao_divida` -> resolver divida tecnica (`todo_marker`/
   `missing_docstring`) em M arquivos distintos (afeta
   manutenibilidade).
4. `crescimento` -> projetar crescimento do repositorio em N arquivos
   novos SEM corrigir nem introduzir nenhum problema - efeito puro de
   diluicao no denominador (complexidade/manutenibilidade sobem so
   porque o total de arquivos cresce; coesao cai se os N novos
   arquivos nao seguirem a convencao de 1 classe).
5. `migracao` -> projetar remover M arquivos do escopo (ex.: extrair
   um modulo para outro repositorio), removendo tambem os problemas
   que esses arquivos especificamente continham - efeito oposto ao
   crescimento.

Teste de paridade (`test_m129`): garante que as formulas puras deste
modulo, alimentadas com os MESMOS contadores que a Missao 127 usou no
calculo ao vivo, reproduzem EXATAMENTE a mesma pontuacao publicada por
`score_report()` - prova de que nao e uma matematica paralela
decorativa, e sim a mesma formula.
"""

from __future__ import annotations

from typing import Any

from app.services.architecture_scoring_service import ContinuousArchitectureScoringService

_SCENARIO_DESCRIPTIONS: dict[str, str] = {
    "novo_modulo": "Adicionar um novo arquivo de servico (e, opcionalmente, um novo modulo de rota).",
    "refatoracao": "Resolver K ocorrencias de long_function ja existentes no backlog.",
    "correcao_divida": "Resolver divida tecnica (todo_marker/missing_docstring) em M arquivos distintos.",
    "crescimento": "Projetar crescimento do repositorio em N arquivos, sem corrigir nem introduzir problemas.",
    "migracao": "Projetar remocao de M arquivos do escopo (ex.: extracao para outro repositorio).",
}


def _modularity_formula(clean_count: int, total_checks: int = 3) -> float:
    """Mesma formula de `ContinuousArchitectureScoringService.modularity_score()`."""
    return round((clean_count / total_checks) * 100, 2) if total_checks else 0.0


def _coupling_formula(via_container_count: int, total_route_modules: int) -> float:
    """Mesma formula de `ContinuousArchitectureScoringService.coupling_score()`."""
    return round((via_container_count / total_route_modules) * 100, 2) if total_route_modules else 0.0


def _cohesion_formula(single_class_files: int, total_files: int) -> float:
    """Mesma formula de `ContinuousArchitectureScoringService.cohesion_score()`."""
    return round((single_class_files / total_files) * 100, 2) if total_files else 0.0


def _complexity_formula(long_function_count: int, total_files: int) -> float:
    """Mesma formula de `ContinuousArchitectureScoringService.complexity_score()`."""
    ratio_clean = 1.0 - (long_function_count / total_files) if total_files else 1.0
    return round(max(0.0, min(1.0, ratio_clean)) * 100, 2)


def _maintainability_formula(files_with_debt: int, total_files: int) -> float:
    """Mesma formula de `ContinuousArchitectureScoringService.maintainability_score()`."""
    ratio_clean = 1.0 - (files_with_debt / total_files) if total_files else 1.0
    return round(max(0.0, min(1.0, ratio_clean)) * 100, 2)


class EngineeringDigitalTwinService:
    """Missao 129. Sem `db` no construtor - a unica dependencia,
    `ContinuousArchitectureScoringService` (Missao 127), tambem nao
    depende de banco."""

    def __init__(self, architecture_scoring: ContinuousArchitectureScoringService | None = None) -> None:
        self.architecture_scoring = architecture_scoring or ContinuousArchitectureScoringService()

    def _baseline(self) -> dict[str, Any]:
        """Extrai os contadores brutos reais que alimentam cada formula
        da Missao 127, a partir do relatorio ao vivo dela. Chamado uma
        vez por simulacao (ou repassado entre simulacoes via o
        parametro `baseline=` para evitar recalculo redundante)."""
        report = self.architecture_scoring.score_report()
        dims = report["dimensions"]

        audit_raw = dims["modularity"]["raw"]
        clean_count = sum(
            1
            for key in ("config_centralization", "route_discovery", "route_collisions")
            if audit_raw[key]["clean"]
        )

        coupling_raw = dims["coupling"]["raw"]
        via_container_count = len(coupling_raw["via_container"])
        total_route_modules = coupling_raw["total_route_modules"]

        cohesion_raw = dims["cohesion"]["raw"]
        total_service_files = len(cohesion_raw)
        single_class_files = sum(1 for count in cohesion_raw.values() if count == 1)

        complexity_raw = dims["complexity"]["raw"]
        total_files_scanned = complexity_raw["total_files_scanned"]
        long_function_count = complexity_raw["rule_counts"].get("long_function", 0)

        maintainability_raw = dims["maintainability"]["raw"]
        files_with_debt = maintainability_raw["summary"]["files_with_debt"]

        return {
            "generated_at": report["generated_at"],
            "overall_score": report["overall_score"],
            "modularity": {"clean_count": clean_count, "total_checks": 3},
            "coupling": {
                "via_container_count": via_container_count,
                "total_route_modules": total_route_modules,
            },
            "cohesion": {
                "single_class_files": single_class_files,
                "total_service_files": total_service_files,
            },
            "complexity": {
                "long_function_count": long_function_count,
                "total_files_scanned": total_files_scanned,
            },
            "maintainability": {
                "files_with_debt": files_with_debt,
                "total_files_scanned": total_files_scanned,
            },
        }

    # --- cenarios -----------------------------------------------------------

    def simulate_new_module(
        self,
        follows_convention: bool = True,
        adds_route: bool = False,
        route_uses_container: bool = True,
        *,
        baseline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        baseline = baseline if baseline is not None else self._baseline()
        coh = baseline["cohesion"]
        new_total = coh["total_service_files"] + 1
        new_single = coh["single_class_files"] + (1 if follows_convention else 0)
        cohesion_before = _cohesion_formula(coh["single_class_files"], coh["total_service_files"])
        cohesion_after = _cohesion_formula(new_single, new_total)

        result: dict[str, Any] = {
            "scenario": "novo_modulo",
            "parameters": {
                "follows_convention": follows_convention,
                "adds_route": adds_route,
                "route_uses_container": route_uses_container,
            },
            "cohesion": {
                "before": cohesion_before,
                "after": cohesion_after,
                "delta": round(cohesion_after - cohesion_before, 2),
            },
        }

        if adds_route:
            coup = baseline["coupling"]
            new_total_routes = coup["total_route_modules"] + 1
            new_via_container = coup["via_container_count"] + (1 if route_uses_container else 0)
            coupling_before = _coupling_formula(coup["via_container_count"], coup["total_route_modules"])
            coupling_after = _coupling_formula(new_via_container, new_total_routes)
            result["coupling"] = {
                "before": coupling_before,
                "after": coupling_after,
                "delta": round(coupling_after - coupling_before, 2),
            }

        return result

    def simulate_refactor_long_functions(
        self, functions_resolved: int, *, baseline: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if functions_resolved < 0:
            raise ValueError("functions_resolved nao pode ser negativo")
        baseline = baseline if baseline is not None else self._baseline()
        comp = baseline["complexity"]
        new_count = max(0, comp["long_function_count"] - functions_resolved)
        before = _complexity_formula(comp["long_function_count"], comp["total_files_scanned"])
        after = _complexity_formula(new_count, comp["total_files_scanned"])
        return {
            "scenario": "refatoracao",
            "parameters": {"functions_resolved": functions_resolved},
            "complexity": {
                "before": before,
                "after": after,
                "delta": round(after - before, 2),
                "remaining_long_functions": new_count,
            },
        }

    def simulate_debt_cleanup(
        self, files_cleaned: int, *, baseline: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if files_cleaned < 0:
            raise ValueError("files_cleaned nao pode ser negativo")
        baseline = baseline if baseline is not None else self._baseline()
        maint = baseline["maintainability"]
        new_files_with_debt = max(0, maint["files_with_debt"] - files_cleaned)
        before = _maintainability_formula(maint["files_with_debt"], maint["total_files_scanned"])
        after = _maintainability_formula(new_files_with_debt, maint["total_files_scanned"])
        return {
            "scenario": "correcao_divida",
            "parameters": {"files_cleaned": files_cleaned},
            "maintainability": {
                "before": before,
                "after": after,
                "delta": round(after - before, 2),
                "remaining_files_with_debt": new_files_with_debt,
            },
        }

    def simulate_growth(
        self,
        new_files: int,
        new_files_follow_convention: bool = True,
        *,
        baseline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if new_files < 0:
            raise ValueError("new_files nao pode ser negativo")
        baseline = baseline if baseline is not None else self._baseline()
        comp = baseline["complexity"]
        maint = baseline["maintainability"]
        coh = baseline["cohesion"]

        new_total_files = comp["total_files_scanned"] + new_files
        complexity_before = _complexity_formula(comp["long_function_count"], comp["total_files_scanned"])
        complexity_after = _complexity_formula(comp["long_function_count"], new_total_files)

        maintainability_before = _maintainability_formula(
            maint["files_with_debt"], maint["total_files_scanned"]
        )
        maintainability_after = _maintainability_formula(maint["files_with_debt"], new_total_files)

        new_total_service_files = coh["total_service_files"] + new_files
        new_single_class_files = coh["single_class_files"] + (
            new_files if new_files_follow_convention else 0
        )
        cohesion_before = _cohesion_formula(coh["single_class_files"], coh["total_service_files"])
        cohesion_after = _cohesion_formula(new_single_class_files, new_total_service_files)

        return {
            "scenario": "crescimento",
            "parameters": {"new_files": new_files, "new_files_follow_convention": new_files_follow_convention},
            "complexity": {
                "before": complexity_before,
                "after": complexity_after,
                "delta": round(complexity_after - complexity_before, 2),
            },
            "maintainability": {
                "before": maintainability_before,
                "after": maintainability_after,
                "delta": round(maintainability_after - maintainability_before, 2),
            },
            "cohesion": {
                "before": cohesion_before,
                "after": cohesion_after,
                "delta": round(cohesion_after - cohesion_before, 2),
            },
        }

    def simulate_migration(
        self,
        files_removed: int,
        long_functions_removed: int = 0,
        debt_files_removed: int = 0,
        *,
        baseline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if files_removed < 0 or long_functions_removed < 0 or debt_files_removed < 0:
            raise ValueError("parametros de migracao nao podem ser negativos")
        baseline = baseline if baseline is not None else self._baseline()
        comp = baseline["complexity"]
        maint = baseline["maintainability"]

        new_total_files = max(0, comp["total_files_scanned"] - files_removed)
        new_long_function_count = max(0, comp["long_function_count"] - long_functions_removed)
        new_files_with_debt = max(0, maint["files_with_debt"] - debt_files_removed)

        complexity_before = _complexity_formula(comp["long_function_count"], comp["total_files_scanned"])
        complexity_after = _complexity_formula(new_long_function_count, new_total_files)

        maintainability_before = _maintainability_formula(
            maint["files_with_debt"], maint["total_files_scanned"]
        )
        maintainability_after = _maintainability_formula(new_files_with_debt, new_total_files)

        return {
            "scenario": "migracao",
            "parameters": {
                "files_removed": files_removed,
                "long_functions_removed": long_functions_removed,
                "debt_files_removed": debt_files_removed,
            },
            "complexity": {
                "before": complexity_before,
                "after": complexity_after,
                "delta": round(complexity_after - complexity_before, 2),
            },
            "maintainability": {
                "before": maintainability_before,
                "after": maintainability_after,
                "delta": round(maintainability_after - maintainability_before, 2),
            },
        }

    _SCENARIO_DISPATCH_NAMES = (
        "novo_modulo",
        "refatoracao",
        "correcao_divida",
        "crescimento",
        "migracao",
    )

    def simulate(self, scenario: str, **kwargs: Any) -> dict[str, Any]:
        """Despacho generico por nome de cenario - usado por integracoes
        futuras (ex.: Missao 130/131) que precisem avaliar um cenario
        especifico sem conhecer o metodo exato."""
        dispatch = {
            "novo_modulo": self.simulate_new_module,
            "refatoracao": self.simulate_refactor_long_functions,
            "correcao_divida": self.simulate_debt_cleanup,
            "crescimento": self.simulate_growth,
            "migracao": self.simulate_migration,
        }
        if scenario not in dispatch:
            raise ValueError(
                f"cenario desconhecido: {scenario!r}. Use um de {sorted(dispatch)}"
            )
        return dispatch[scenario](**kwargs)

    def available_scenarios(self) -> dict[str, str]:
        return dict(_SCENARIO_DESCRIPTIONS)

    def digital_twin_report(self) -> dict[str, Any]:
        """Relatorio de demonstracao: calcula a linha de base UMA vez
        (evitando recalcular `score_report()` da Missao 127 cinco
        vezes) e roda os 5 tipos de cenario com parametros ilustrativos
        default. Os parametros default sao exemplos, nao recomendacoes -
        quem quiser avaliar uma mudanca real deve chamar `simulate()`
        com os parametros da mudanca em questao."""
        baseline = self._baseline()
        return {
            "generated_at": baseline["generated_at"],
            "overall_score_now": baseline["overall_score"],
            "scenarios": {
                "novo_modulo": self.simulate_new_module(
                    follows_convention=True, adds_route=False, baseline=baseline
                ),
                "refatoracao": self.simulate_refactor_long_functions(
                    functions_resolved=1, baseline=baseline
                ),
                "correcao_divida": self.simulate_debt_cleanup(files_cleaned=1, baseline=baseline),
                "crescimento": self.simulate_growth(
                    new_files=10, new_files_follow_convention=True, baseline=baseline
                ),
                "migracao": self.simulate_migration(
                    files_removed=5,
                    long_functions_removed=2,
                    debt_files_removed=2,
                    baseline=baseline,
                ),
            },
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.digital_twin_report()

        lines: list[str] = [
            "# Gemeo Digital de Engenharia (Missao 129)",
            "",
            f"- Gerado em: {report['generated_at']}",
            f"- Pontuacao geral atual (Missao 127, ao vivo): {report['overall_score_now']}/100",
            "",
            "## Cenarios simulados (what-if, nada foi aplicado)",
            "",
        ]

        for name, sim in report["scenarios"].items():
            lines.append(f"### {name}")
            lines.append(f"Parametros: {sim['parameters']}")
            for dim_name, dim_data in sim.items():
                if dim_name in ("scenario", "parameters"):
                    continue
                lines.append(
                    f"- {dim_name}: {dim_data['before']} -> {dim_data['after']} "
                    f"(delta {dim_data['delta']:+.2f})"
                )
            lines.append("")

        lines.append(
            "**IMPORTANTE**: nenhum cenario acima foi aplicado de fato no "
            "repositorio - sao simulacoes que partem do estado real ao vivo "
            "(Missao 127) e aplicam as mesmas formulas documentadas naquela "
            "missao a parametros hipoteticos explicitos. Os parametros usados "
            "aqui sao exemplos ilustrativos, nao recomendacoes; chame "
            "`simulate(cenario, **parametros)` com os numeros de uma mudanca "
            "real para avalia-la antes de implementa-la."
        )

        return "\n".join(lines)
