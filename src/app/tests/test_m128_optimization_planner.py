"""Missao 128 - Autonomous Optimization Planner.

Cobertura:
1. Fakes com contador de chamadas para TechDebtManagerService (M58) e
   ContinuousArchitectureScoringService (M127) - prova de reuso direto.
2. Mapeamento regra -> dimensao (long_function -> complexity;
   todo_marker/missing_docstring -> maintainability).
3. Ganho esperado: formula linear para complexity (sempre
   100/total_files); para maintainability, so quando o item e o ultimo
   de divida do seu arquivo no backlog atual.
4. Impacto: "alto" quando a dimensao esta em attention_dimensions
   (M127, ao vivo), "moderado" senao.
5. Esforco estimado (heuristica) por tipo de regra.
6. Agregacao (total_recommendations, high_impact_count,
   total_expected_gain_points, source_total_priority_score).
7. render_markdown() - com e sem recomendacoes.
8. Smoke test contra o repositorio real.
9. Ausencia deliberada em registered_providers() (mesmo padrao M55/56/58/59/127).
10. Endpoints HTTP /live e /markdown, incluindo override de DI.
"""

from __future__ import annotations

from app.core.container import get_optimization_planner_service, registered_providers
from app.main import app as real_app
from app.services.optimization_planner_service import AutonomousOptimizationPlannerService
from fastapi.testclient import TestClient


def _service(**kwargs) -> AutonomousOptimizationPlannerService:
    return AutonomousOptimizationPlannerService(**kwargs)


class _FakeTechDebtManager:
    def __init__(self, backlog: list[dict], total_priority_score: int = 0) -> None:
        self._backlog = backlog
        self._total_priority_score = total_priority_score
        self.calls = 0

    def debt_report(self) -> dict:
        self.calls += 1
        return {
            "summary": {"total_priority_score": self._total_priority_score},
            "backlog": self._backlog,
        }


class _FakeArchitectureScoring:
    def __init__(self, total_files_scanned: int = 10, attention_dimensions: tuple = ()) -> None:
        self._total_files_scanned = total_files_scanned
        self._attention_dimensions = list(attention_dimensions)
        self.calls = 0

    def score_report(self) -> dict:
        self.calls += 1
        return {
            "attention_dimensions": self._attention_dimensions,
            "dimensions": {
                "complexity": {"raw": {"total_files_scanned": self._total_files_scanned}},
            },
        }


def _debt_item(file: str, rule: str, priority_score: int = 1, line: int = 1) -> dict:
    return {
        "file": file,
        "line": line,
        "rule": rule,
        "detail": f"detalhe de {rule}",
        "age_days": 10,
        "age_known": True,
        "priority_score": priority_score,
    }


# --- reuso direto, sem reimplementar ----------------------------------------


def test_optimization_plan_calls_both_engines_exactly_once():
    debt_fake = _FakeTechDebtManager(backlog=[])
    scoring_fake = _FakeArchitectureScoring()
    svc = _service(tech_debt_manager=debt_fake, architecture_scoring=scoring_fake)
    svc.optimization_plan()
    assert debt_fake.calls == 1
    assert scoring_fake.calls == 1


def test_optimization_plan_preserves_backlog_order_as_priority_rank():
    backlog = [
        _debt_item("b.py", "todo_marker", priority_score=30),
        _debt_item("a.py", "missing_docstring", priority_score=10),
    ]
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=backlog),
        architecture_scoring=_FakeArchitectureScoring(),
    )
    plan = svc.optimization_plan()
    ranks = [r["priority_rank"] for r in plan["recommendations"]]
    assert ranks == [1, 2]
    assert plan["recommendations"][0]["file"] == "b.py"
    assert plan["recommendations"][0]["priority_score"] == 30


# --- mapeamento regra -> dimensao e ganho esperado --------------------------


def test_long_function_maps_to_complexity_with_linear_gain():
    backlog = [_debt_item("a.py", "long_function")]
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=backlog),
        architecture_scoring=_FakeArchitectureScoring(total_files_scanned=20),
    )
    rec = svc.optimization_plan()["recommendations"][0]
    assert rec["affected_dimension"] == "complexity"
    assert rec["expected_gain_points"] == 5.0  # 100/20


def test_todo_marker_maps_to_maintainability_and_gains_only_if_last_in_file():
    backlog = [
        _debt_item("shared.py", "todo_marker", line=1),
        _debt_item("shared.py", "missing_docstring", line=2),
        _debt_item("alone.py", "todo_marker", line=1),
    ]
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=backlog),
        architecture_scoring=_FakeArchitectureScoring(total_files_scanned=10),
    )
    recs = svc.optimization_plan()["recommendations"]
    shared_items = [r for r in recs if r["file"] == "shared.py"]
    alone_item = next(r for r in recs if r["file"] == "alone.py")

    for rec in shared_items:
        assert rec["affected_dimension"] == "maintainability"
        assert rec["expected_gain_points"] == 0.0  # shared.py tem 2 itens, nenhum e o ultimo

    assert alone_item["expected_gain_points"] == 10.0  # 100/10, unico item do arquivo


def test_expected_gain_is_zero_when_total_files_scanned_is_zero():
    backlog = [_debt_item("a.py", "long_function")]
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=backlog),
        architecture_scoring=_FakeArchitectureScoring(total_files_scanned=0),
    )
    rec = svc.optimization_plan()["recommendations"][0]
    assert rec["expected_gain_points"] == 0.0


# --- impacto -----------------------------------------------------------------


def test_impact_is_alto_when_dimension_is_in_attention():
    backlog = [_debt_item("a.py", "long_function")]
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=backlog),
        architecture_scoring=_FakeArchitectureScoring(attention_dimensions=("complexity",)),
    )
    rec = svc.optimization_plan()["recommendations"][0]
    assert rec["impact"] == "alto"


def test_impact_is_moderado_when_dimension_is_not_in_attention():
    backlog = [_debt_item("a.py", "long_function")]
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=backlog),
        architecture_scoring=_FakeArchitectureScoring(attention_dimensions=("maintainability",)),
    )
    rec = svc.optimization_plan()["recommendations"][0]
    assert rec["impact"] == "moderado"


# --- esforco estimado (heuristica) -------------------------------------------


def test_estimated_effort_follows_documented_heuristic_tiers():
    backlog = [
        _debt_item("a.py", "long_function", line=1),
        _debt_item("a.py", "todo_marker", line=2),
        _debt_item("a.py", "missing_docstring", line=3),
    ]
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=backlog),
        architecture_scoring=_FakeArchitectureScoring(),
    )
    recs = {r["rule"]: r["estimated_effort"] for r in svc.optimization_plan()["recommendations"]}
    assert recs["long_function"] == "alto"
    assert recs["todo_marker"] == "medio"
    assert recs["missing_docstring"] == "baixo"


# --- agregacao -----------------------------------------------------------------


def test_aggregation_fields_are_computed_correctly():
    backlog = [
        _debt_item("a.py", "long_function", line=1),
        _debt_item("b.py", "todo_marker", line=1),
    ]
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=backlog, total_priority_score=99),
        architecture_scoring=_FakeArchitectureScoring(
            total_files_scanned=10, attention_dimensions=("complexity",)
        ),
    )
    plan = svc.optimization_plan()
    assert plan["total_recommendations"] == 2
    assert plan["high_impact_count"] == 1  # so o long_function (complexity em attention)
    assert plan["source_total_priority_score"] == 99
    # a.py (long_function, unico item) -> 100/10 = 10.0 em complexity
    # b.py (todo_marker, unico item do arquivo) -> 100/10 = 10.0 em maintainability
    assert plan["total_expected_gain_points"] == 20.0


def test_aggregation_with_empty_backlog():
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=[]),
        architecture_scoring=_FakeArchitectureScoring(),
    )
    plan = svc.optimization_plan()
    assert plan["total_recommendations"] == 0
    assert plan["high_impact_count"] == 0
    assert plan["recommendations"] == []


# --- render_markdown -----------------------------------------------------------


def test_render_markdown_lists_top_recommendations():
    backlog = [_debt_item("a.py", "long_function", priority_score=50)]
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=backlog),
        architecture_scoring=_FakeArchitectureScoring(),
    )
    text = svc.render_markdown()
    assert "a.py" in text
    assert "long_function" in text
    assert "IMPORTANTE" in text


def test_render_markdown_handles_empty_backlog():
    svc = _service(
        tech_debt_manager=_FakeTechDebtManager(backlog=[]),
        architecture_scoring=_FakeArchitectureScoring(),
    )
    text = svc.render_markdown()
    assert "nenhuma melhoria pendente" in text


# --- smoke test contra o repositorio real -------------------------------------


def test_optimization_plan_against_real_repository_has_well_typed_fields():
    svc = _service()
    plan = svc.optimization_plan()
    assert isinstance(plan["total_recommendations"], int)
    assert plan["total_recommendations"] >= 0
    for rec in plan["recommendations"][:5]:
        assert rec["affected_dimension"] in ("complexity", "maintainability", None)
        assert rec["impact"] in ("alto", "moderado")
        assert rec["estimated_effort"] in ("alto", "medio", "baixo", "desconhecido")
        assert isinstance(rec["expected_gain_points"], float)
    assert isinstance(svc.render_markdown(plan), str)


# --- registro via container ----------------------------------------------------


def test_optimization_planner_service_is_not_in_the_provider_registry():
    # mesmo padrao de get_architecture_audit_service/55, get_code_review_service/56,
    # get_tech_debt_manager_service/58, get_architecture_stress_test_service/59 e
    # get_architecture_scoring_service/127: nao depende de db, por isso nao usa
    # provide() e nao aparece em registered_providers(), de proposito.
    assert "AutonomousOptimizationPlannerService" not in registered_providers()


# --- endpoints HTTP --------------------------------------------------------------


def test_optimization_planner_live_endpoint_returns_real_computed_plan():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/optimization-planner/live")
    assert response.status_code == 200
    body = response.json()
    assert "recommendations" in body
    assert "total_recommendations" in body


def test_optimization_planner_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/optimization-planner/markdown")
    assert response.status_code == 200
    assert "Planejador Autonomo de Otimizacao" in response.text


def test_optimization_planner_endpoint_is_overridable_via_container_not_hardcoded():
    fake_plan = {"total_recommendations": 0, "recommendations": []}

    class _StubService:
        def optimization_plan(self):
            return fake_plan

    def _override():
        return _StubService()

    real_app.dependency_overrides[get_optimization_planner_service] = _override
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/optimization-planner/live")
        assert response.json() == fake_plan
    finally:
        del real_app.dependency_overrides[get_optimization_planner_service]
