"""Missao 129 - Engineering Digital Twin.

Cobertura:
1. Fake de ContinuousArchitectureScoringService (M127) com contador de
   chamadas - prova de que a linha de base vem do estado ao vivo real.
2. Cada um dos 5 cenarios (novo_modulo, refatoracao, correcao_divida,
   crescimento, migracao) com aritmetica verificada a mao.
3. Reuso de `baseline=` evita recalculo redundante (digital_twin_report
   so chama score_report() uma vez, nao 5).
4. Validacao de parametros negativos.
5. Dispatcher generico `simulate()` e `available_scenarios()`.
6. Teste de PARIDADE: as formulas puras deste modulo, alimentadas com
   os mesmos contadores que a Missao 127 usa ao vivo, reproduzem
   exatamente a mesma pontuacao publicada por score_report() - prova
   de que nao e matematica decorativa paralela.
7. Smoke test contra o repositorio real.
8. Ausencia deliberada em registered_providers() (mesmo padrao M55/56/58/59/127/128).
9. Endpoints HTTP /live e /markdown, incluindo override de DI.
"""

from __future__ import annotations

from app.core.container import get_digital_twin_service, registered_providers
from app.main import app as real_app
from app.services.architecture_scoring_service import ContinuousArchitectureScoringService
from app.services.digital_twin_service import EngineeringDigitalTwinService
from fastapi.testclient import TestClient


def _service(**kwargs) -> EngineeringDigitalTwinService:
    return EngineeringDigitalTwinService(**kwargs)


def _fake_score_report(
    *,
    config_clean: bool = True,
    route_discovery_clean: bool = True,
    route_collisions_clean: bool = True,
    via_container: tuple = ("a", "b"),
    total_route_modules: int = 10,
    file_class_counts: dict | None = None,
    total_files_scanned: int = 20,
    long_function_count: int = 4,
    files_with_debt: int = 6,
    overall_score: float = 55.0,
) -> dict:
    file_class_counts = file_class_counts if file_class_counts is not None else {
        "a.py": 1, "b.py": 1, "c.py": 2,
    }
    return {
        "generated_at": "2026-06-28T00:00:00Z",
        "overall_score": overall_score,
        "dimensions": {
            "modularity": {
                "raw": {
                    "config_centralization": {"clean": config_clean},
                    "route_discovery": {"clean": route_discovery_clean},
                    "route_collisions": {"clean": route_collisions_clean},
                }
            },
            "coupling": {
                "raw": {
                    "via_container": list(via_container),
                    "total_route_modules": total_route_modules,
                }
            },
            "cohesion": {"raw": file_class_counts},
            "complexity": {
                "raw": {
                    "total_files_scanned": total_files_scanned,
                    "rule_counts": {"long_function": long_function_count},
                }
            },
            "maintainability": {
                "raw": {"summary": {"files_with_debt": files_with_debt}}
            },
        },
    }


class _FakeArchitectureScoring:
    def __init__(self, **report_kwargs) -> None:
        self._report_kwargs = report_kwargs
        self.calls = 0

    def score_report(self) -> dict:
        self.calls += 1
        return _fake_score_report(**self._report_kwargs)


# --- baseline vem do estado ao vivo real -------------------------------------


def test_baseline_calls_architecture_scoring_exactly_once_per_simulation():
    fake = _FakeArchitectureScoring()
    svc = _service(architecture_scoring=fake)
    svc.simulate_refactor_long_functions(functions_resolved=1)
    assert fake.calls == 1


def test_digital_twin_report_computes_baseline_only_once_for_all_five_scenarios():
    fake = _FakeArchitectureScoring()
    svc = _service(architecture_scoring=fake)
    svc.digital_twin_report()
    assert fake.calls == 1  # nao 5 - baseline reusado via parametro `baseline=`


# --- cenario: novo_modulo ------------------------------------------------------


def test_simulate_new_module_follows_convention_improves_cohesion():
    fake = _FakeArchitectureScoring(
        file_class_counts={"a.py": 1, "b.py": 1, "c.py": 2}  # 2/3 = 66.67
    )
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_new_module(follows_convention=True)
    assert sim["cohesion"]["before"] == 66.67
    assert sim["cohesion"]["after"] == 75.0  # 3/4
    assert sim["cohesion"]["delta"] == 8.33
    assert "coupling" not in sim  # adds_route=False por padrao


def test_simulate_new_module_breaking_convention_hurts_cohesion():
    fake = _FakeArchitectureScoring(file_class_counts={"a.py": 1, "b.py": 1})  # 2/2 = 100
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_new_module(follows_convention=False)
    assert sim["cohesion"]["before"] == 100.0
    assert sim["cohesion"]["after"] == 66.67  # 2/3
    assert sim["cohesion"]["delta"] == -33.33


def test_simulate_new_module_with_route_using_container_improves_coupling():
    fake = _FakeArchitectureScoring(via_container=("a", "b"), total_route_modules=10)  # 20%
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_new_module(adds_route=True, route_uses_container=True)
    assert sim["coupling"]["before"] == 20.0
    assert sim["coupling"]["after"] == 27.27  # 3/11
    assert sim["coupling"]["delta"] == 7.27


def test_simulate_new_module_with_route_not_using_container_hurts_coupling():
    fake = _FakeArchitectureScoring(via_container=("a", "b"), total_route_modules=10)  # 20%
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_new_module(adds_route=True, route_uses_container=False)
    assert sim["coupling"]["before"] == 20.0
    assert sim["coupling"]["after"] == 18.18  # 2/11
    assert sim["coupling"]["delta"] == -1.82


# --- cenario: refatoracao -------------------------------------------------------


def test_simulate_refactor_long_functions_improves_complexity():
    fake = _FakeArchitectureScoring(long_function_count=4, total_files_scanned=20)  # 1-4/20=80
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_refactor_long_functions(functions_resolved=2)
    assert sim["complexity"]["before"] == 80.0
    assert sim["complexity"]["after"] == 90.0  # 1-2/20
    assert sim["complexity"]["remaining_long_functions"] == 2


def test_simulate_refactor_clamps_at_zero_remaining():
    fake = _FakeArchitectureScoring(long_function_count=2, total_files_scanned=20)
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_refactor_long_functions(functions_resolved=10)
    assert sim["complexity"]["remaining_long_functions"] == 0
    assert sim["complexity"]["after"] == 100.0


def test_simulate_refactor_rejects_negative_input():
    svc = _service(architecture_scoring=_FakeArchitectureScoring())
    try:
        svc.simulate_refactor_long_functions(functions_resolved=-1)
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass


# --- cenario: correcao_divida ---------------------------------------------------


def test_simulate_debt_cleanup_improves_maintainability():
    fake = _FakeArchitectureScoring(files_with_debt=6, total_files_scanned=20)  # 1-6/20=70
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_debt_cleanup(files_cleaned=3)
    assert sim["maintainability"]["before"] == 70.0
    assert sim["maintainability"]["after"] == 85.0  # 1-3/20
    assert sim["maintainability"]["remaining_files_with_debt"] == 3


# --- cenario: crescimento -------------------------------------------------------


def test_simulate_growth_dilutes_complexity_and_maintainability_without_fixing_anything():
    fake = _FakeArchitectureScoring(
        long_function_count=4,
        files_with_debt=6,
        total_files_scanned=20,
        file_class_counts={"a.py": 1, "b.py": 1},  # 2/2=100
    )
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_growth(new_files=10, new_files_follow_convention=True)
    # complexidade: 1-4/20=80 -> 1-4/30=86.67 (sobe so por diluicao, sem corrigir nada)
    assert sim["complexity"]["before"] == 80.0
    assert sim["complexity"]["after"] == 86.67
    # manutenibilidade: 1-6/20=70 -> 1-6/30=80.0
    assert sim["maintainability"]["before"] == 70.0
    assert sim["maintainability"]["after"] == 80.0
    # coesao: 2/2=100 -> 12/12=100 (novos arquivos seguem a convencao)
    assert sim["cohesion"]["before"] == 100.0
    assert sim["cohesion"]["after"] == 100.0


def test_simulate_growth_with_files_breaking_convention_hurts_cohesion():
    fake = _FakeArchitectureScoring(file_class_counts={"a.py": 1, "b.py": 1})  # 2/2=100
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_growth(new_files=2, new_files_follow_convention=False)
    assert sim["cohesion"]["before"] == 100.0
    assert sim["cohesion"]["after"] == 50.0  # 2/4


# --- cenario: migracao ----------------------------------------------------------


def test_simulate_migration_removes_files_and_their_problems():
    fake = _FakeArchitectureScoring(
        long_function_count=4, files_with_debt=6, total_files_scanned=20
    )
    svc = _service(architecture_scoring=fake)
    sim = svc.simulate_migration(files_removed=5, long_functions_removed=2, debt_files_removed=3)
    # complexidade: 1-4/20=80 -> 1-2/15=86.67
    assert sim["complexity"]["before"] == 80.0
    assert sim["complexity"]["after"] == 86.67
    # manutenibilidade: 1-6/20=70 -> 1-3/15=80.0
    assert sim["maintainability"]["before"] == 70.0
    assert sim["maintainability"]["after"] == 80.0


def test_simulate_migration_rejects_negative_input():
    svc = _service(architecture_scoring=_FakeArchitectureScoring())
    try:
        svc.simulate_migration(files_removed=-1)
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass


# --- dispatcher generico e descricoes -------------------------------------------


def test_simulate_dispatches_to_the_correct_scenario_method():
    fake = _FakeArchitectureScoring(long_function_count=4, total_files_scanned=20)
    svc = _service(architecture_scoring=fake)
    via_method = svc.simulate_refactor_long_functions(functions_resolved=1)
    via_dispatch = svc.simulate("refatoracao", functions_resolved=1)
    assert via_method == via_dispatch


def test_simulate_raises_on_unknown_scenario():
    svc = _service(architecture_scoring=_FakeArchitectureScoring())
    try:
        svc.simulate("cenario_inexistente")
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass


def test_available_scenarios_lists_all_five():
    svc = _service(architecture_scoring=_FakeArchitectureScoring())
    scenarios = svc.available_scenarios()
    assert set(scenarios) == {
        "novo_modulo", "refatoracao", "correcao_divida", "crescimento", "migracao",
    }


# --- render_markdown --------------------------------------------------------------


def test_render_markdown_includes_all_scenarios_and_disclaimer():
    fake = _FakeArchitectureScoring()
    svc = _service(architecture_scoring=fake)
    text = svc.render_markdown()
    for name in ("novo_modulo", "refatoracao", "correcao_divida", "crescimento", "migracao"):
        assert name in text
    assert "IMPORTANTE" in text
    assert "nenhum cenario acima foi aplicado de fato" in text


# --- teste de PARIDADE com a Missao 127 ao vivo -----------------------------------


def test_pure_formulas_match_real_m127_score_report_exactly():
    real_scoring = ContinuousArchitectureScoringService()
    real_report = real_scoring.score_report()
    real_dims = real_report["dimensions"]

    svc = _service(architecture_scoring=real_scoring)
    baseline = svc._baseline()

    # modularidade
    from app.services.digital_twin_service import _modularity_formula
    assert _modularity_formula(baseline["modularity"]["clean_count"]) == real_dims["modularity"]["score"]

    # acoplamento
    from app.services.digital_twin_service import _coupling_formula
    coup = baseline["coupling"]
    assert (
        _coupling_formula(coup["via_container_count"], coup["total_route_modules"])
        == real_dims["coupling"]["score"]
    )

    # coesao
    from app.services.digital_twin_service import _cohesion_formula
    coh = baseline["cohesion"]
    assert (
        _cohesion_formula(coh["single_class_files"], coh["total_service_files"])
        == real_dims["cohesion"]["score"]
    )

    # complexidade
    from app.services.digital_twin_service import _complexity_formula
    comp = baseline["complexity"]
    assert (
        _complexity_formula(comp["long_function_count"], comp["total_files_scanned"])
        == real_dims["complexity"]["score"]
    )

    # manutenibilidade
    from app.services.digital_twin_service import _maintainability_formula
    maint = baseline["maintainability"]
    assert (
        _maintainability_formula(maint["files_with_debt"], maint["total_files_scanned"])
        == real_dims["maintainability"]["score"]
    )


# --- smoke test contra o repositorio real -----------------------------------------


def test_digital_twin_report_against_real_repository_has_well_typed_fields():
    svc = _service()
    report = svc.digital_twin_report()
    assert isinstance(report["overall_score_now"], float)
    assert set(report["scenarios"]) == {
        "novo_modulo", "refatoracao", "correcao_divida", "crescimento", "migracao",
    }
    assert isinstance(svc.render_markdown(report), str)


# --- registro via container ----------------------------------------------------


def test_digital_twin_service_is_not_in_the_provider_registry():
    # mesmo padrao de get_architecture_audit_service/55, get_code_review_service/56,
    # get_tech_debt_manager_service/58, get_architecture_stress_test_service/59,
    # get_architecture_scoring_service/127 e get_optimization_planner_service/128:
    # nao depende de db, por isso nao usa provide() e nao aparece em
    # registered_providers(), de proposito.
    assert "EngineeringDigitalTwinService" not in registered_providers()


# --- endpoints HTTP -----------------------------------------------------------------


def test_digital_twin_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/digital-twin/live")
    assert response.status_code == 200
    body = response.json()
    assert "scenarios" in body
    assert "overall_score_now" in body


def test_digital_twin_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/digital-twin/markdown")
    assert response.status_code == 200
    assert "Gemeo Digital de Engenharia" in response.text


def test_digital_twin_endpoint_is_overridable_via_container_not_hardcoded():
    fake_report = {"overall_score_now": 0.0, "scenarios": {}}

    class _StubService:
        def digital_twin_report(self):
            return fake_report

    def _override():
        return _StubService()

    real_app.dependency_overrides[get_digital_twin_service] = _override
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/digital-twin/live")
        assert response.json() == fake_report
    finally:
        del real_app.dependency_overrides[get_digital_twin_service]
