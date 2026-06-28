"""Missao 58 - Automatic Technical Debt Manager. Suite dedicada."""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from app.core.container import get_tech_debt_manager_service, registered_providers
from app.main import app as real_app
from app.services.tech_debt_manager_service import TechDebtManagerService, _run_git


def _service() -> TechDebtManagerService:
    return TechDebtManagerService()


class _FakeCodeReview:
    """Substitui CodeReviewService para testar TechDebtManagerService de
    forma isolada - prova que ele e um agregador puro, mesmo padrao de
    `test_current_snapshot_is_a_pure_aggregator...` da Missao 57."""

    def __init__(self, per_file):
        self._per_file = per_file

    def review_repository(self):
        return {"per_file": self._per_file}


def _finding(rule, line, detail="achado sintetico"):
    return {"rule": rule, "severity": "informative", "line": line, "detail": detail}


# --- _run_git / acesso ao repositorio real --------------------------------------

def test_run_git_executes_against_the_real_project_repository():
    output = _run_git(["rev-parse", "--is-inside-work-tree"])
    assert output.strip() == "true"


def test_run_git_raises_visibly_on_an_invalid_subcommand():
    with pytest.raises(subprocess.CalledProcessError):
        _run_git(["nao-existe-esse-comando"])


# --- mapa de idade por arquivo (1 unica chamada ao git) --------------------------

def test_file_age_days_map_is_built_with_a_single_git_call(monkeypatch):
    call_count = {"n": 0}
    real_run = subprocess.run

    def _counting_run(*args, **kwargs):
        call_count["n"] += 1
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _counting_run)
    service = _service()
    service.debt_items()
    # exatamente 1 chamada git para o mapa de idade + 0 chamadas extras por
    # achado - nunca um subprocesso por item de divida (decisao de
    # performance documentada no modulo).
    assert call_count["n"] == 1


def test_file_age_days_returns_a_real_non_negative_integer_for_a_tracked_file():
    age = _service().file_age_days("services/code_review_service.py")
    assert isinstance(age, int)
    assert age >= 0


def test_file_age_days_returns_none_for_a_file_never_committed():
    age = _service().file_age_days("este/arquivo/nao/existe/no/historico.py")
    assert age is None


# --- debt_items(): so os 3 eixos informativos, nunca os bloqueantes -------------

def test_debt_items_only_includes_the_three_informative_rules_never_blocking():
    per_file = [
        {
            "file": "fake_module.py",
            "findings": [
                {"rule": "bare_except", "severity": "blocking", "line": 1, "detail": "x"},
                _finding("missing_docstring", 2),
                _finding("long_function", 3),
                _finding("todo_marker", 4),
            ],
        }
    ]
    service = TechDebtManagerService(code_review=_FakeCodeReview(per_file))
    items = service.debt_items()
    rules = {item["rule"] for item in items}
    assert rules == {"missing_docstring", "long_function", "todo_marker"}
    assert len(items) == 3


def test_debt_items_against_the_real_repository_matches_code_review_rule_counts():
    """Prova que TechDebtManagerService nao reimplementa deteccao - os
    totais por regra tem que bater exatamente com CodeReviewService."""
    service = _service()
    code_review_report = service.code_review.review_repository()
    items = service.debt_items()
    counted = {}
    for item in items:
        counted[item["rule"]] = counted.get(item["rule"], 0) + 1
    for rule in ("missing_docstring", "long_function", "todo_marker"):
        assert counted[rule] == code_review_report["rule_counts"][rule]


def test_debt_items_have_expected_fields():
    items = _service().debt_items()
    assert items, "repositorio real deveria ter pelo menos um achado informativo"
    sample = items[0]
    for field in ("file", "line", "rule", "detail", "age_days", "age_known", "priority_score"):
        assert field in sample


# --- pontuacao de prioridade: peso de regra x idade ------------------------------

def test_priority_score_weighs_todo_marker_more_than_long_function_more_than_missing_docstring():
    per_file = [
        {
            "file": "a.py",
            "findings": [
                _finding("missing_docstring", 1),
                _finding("long_function", 2),
                _finding("todo_marker", 3),
            ],
        }
    ]
    service = TechDebtManagerService(code_review=_FakeCodeReview(per_file))
    items = {item["rule"]: item for item in service.debt_items()}
    assert items["todo_marker"]["priority_score"] > items["long_function"]["priority_score"]
    assert items["long_function"]["priority_score"] > items["missing_docstring"]["priority_score"]


def test_priority_score_increases_with_age_for_the_same_rule(monkeypatch):
    service = _service()
    monkeypatch.setattr(
        TechDebtManagerService, "_file_age_days_map", staticmethod(lambda: {"old.py": 100, "new.py": 0})
    )
    per_file = [
        {"file": "old.py", "findings": [_finding("missing_docstring", 1)]},
        {"file": "new.py", "findings": [_finding("missing_docstring", 1)]},
    ]
    service.code_review = _FakeCodeReview(per_file)
    items = {item["file"]: item for item in service.debt_items()}
    assert items["old.py"]["priority_score"] > items["new.py"]["priority_score"]
    assert items["old.py"]["age_days"] == 100
    assert items["new.py"]["age_days"] == 0


# --- backlog priorizado ----------------------------------------------------------

def test_prioritized_backlog_is_sorted_descending_by_score():
    items = [
        {"file": "a.py", "priority_score": 5},
        {"file": "b.py", "priority_score": 50},
        {"file": "c.py", "priority_score": 1},
    ]
    backlog = TechDebtManagerService.prioritized_backlog(items)
    assert [item["priority_score"] for item in backlog] == [50, 5, 1]


def test_prioritized_backlog_handles_empty_items_without_crashing():
    assert TechDebtManagerService.prioritized_backlog([]) == []


# --- hotspots: arquivos com mais divida acumulada --------------------------------

def test_hotspots_ranks_files_by_total_score_not_just_count():
    items = [
        {"file": "many_small.py", "priority_score": 1},
        {"file": "many_small.py", "priority_score": 1},
        {"file": "many_small.py", "priority_score": 1},
        {"file": "few_big.py", "priority_score": 50},
    ]
    hotspots = TechDebtManagerService.hotspots(items)
    assert hotspots[0]["file"] == "few_big.py"
    assert hotspots[0]["total_score"] == 50
    assert hotspots[1]["file"] == "many_small.py"
    assert hotspots[1]["debt_item_count"] == 3


def test_hotspots_respects_top_n_limit():
    items = [{"file": f"file_{i}.py", "priority_score": i} for i in range(10)]
    hotspots = TechDebtManagerService.hotspots(items, top_n=3)
    assert len(hotspots) == 3


def test_hotspots_handles_empty_items_without_crashing():
    assert TechDebtManagerService.hotspots([]) == []


# --- summary -----------------------------------------------------------------------

def test_summary_aggregates_counts_and_scores_correctly():
    items = [
        {"file": "a.py", "rule": "todo_marker", "priority_score": 10, "age_days": 5, "age_known": True},
        {"file": "a.py", "rule": "long_function", "priority_score": 4, "age_days": 1, "age_known": True},
        {"file": "b.py", "rule": "missing_docstring", "priority_score": 1, "age_days": 0, "age_known": False},
    ]
    summary = TechDebtManagerService.summary(items)
    assert summary["total_debt_items"] == 3
    assert summary["files_with_debt"] == 2
    assert summary["total_priority_score"] == 15
    assert summary["oldest_item_age_days"] == 5
    assert summary["items_with_unknown_age"] == 1
    assert summary["items_by_rule"] == {
        "long_function": 1,
        "missing_docstring": 1,
        "todo_marker": 1,
    }


def test_summary_oldest_item_age_days_is_zero_when_items_is_empty():
    summary = TechDebtManagerService.summary([])
    assert summary["oldest_item_age_days"] == 0
    assert summary["total_debt_items"] == 0


def test_summary_tracks_items_with_unknown_age():
    items = [
        {"file": "a.py", "rule": "todo_marker", "priority_score": 1, "age_days": 0, "age_known": False},
        {"file": "b.py", "rule": "todo_marker", "priority_score": 1, "age_days": 0, "age_known": False},
    ]
    summary = TechDebtManagerService.summary(items)
    assert summary["items_with_unknown_age"] == 2


# --- relatorio completo e markdown ------------------------------------------------

def test_debt_report_combines_summary_hotspots_and_backlog():
    report = _service().debt_report()
    assert "generated_at" in report
    assert "summary" in report
    assert "hotspots" in report
    assert "backlog" in report
    assert report["summary"]["total_debt_items"] == len(report["backlog"])


def test_render_markdown_mentions_the_total_and_hotspots():
    report = _service().debt_report()
    markdown = _service().render_markdown(report)
    assert "Gestor Automatico de Divida Tecnica" in markdown
    assert str(report["summary"]["total_debt_items"]) in markdown
    if report["hotspots"]:
        assert "Hotspots" in markdown


def test_render_markdown_handles_zero_debt_items_without_crashing():
    service = TechDebtManagerService(code_review=_FakeCodeReview([]))
    markdown = service.render_markdown()
    assert "Gestor Automatico de Divida Tecnica" in markdown
    assert "Itens de divida detectados: 0" in markdown


# --- Container (Missao 52) e endpoints HTTP --------------------------------------

def test_tech_debt_manager_service_itself_is_not_in_the_provider_registry():
    """Mesma decisao documentada nas Missoes 55/56: services sem `db` nao
    usam `provide()`, por isso nao aparecem em `registered_providers()`."""
    assert "TechDebtManagerService" not in registered_providers()


def test_tech_debt_live_endpoint_returns_real_computed_report():
    client = TestClient(real_app)
    response = client.get("/api/v1/tech-debt/live")
    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "backlog" in payload


def test_tech_debt_markdown_endpoint_returns_text():
    client = TestClient(real_app)
    response = client.get("/api/v1/tech-debt/markdown")
    assert response.status_code == 200
    assert "Gestor Automatico de Divida Tecnica" in response.text


def test_tech_debt_endpoint_is_overridable_via_container_not_hardcoded():
    class _FakeManager:
        def debt_report(self):
            return {"generated_at": "now", "summary": {"total_debt_items": 0}, "hotspots": [], "backlog": []}

    real_app.dependency_overrides[get_tech_debt_manager_service] = lambda: _FakeManager()
    try:
        client = TestClient(real_app)
        response = client.get("/api/v1/tech-debt/live")
        assert response.status_code == 200
        assert response.json()["summary"]["total_debt_items"] == 0
    finally:
        real_app.dependency_overrides.pop(get_tech_debt_manager_service, None)
