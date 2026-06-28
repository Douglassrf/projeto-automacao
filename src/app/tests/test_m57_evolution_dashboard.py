"""Missao 57 - Evolution Dashboard.

Contexto coberto por estes testes: as Missoes 51-56 entregaram seis
motores que cada um responde a propria pergunta de saude, mas nenhum
lugar agrega a EVOLUCAO do projeto, missao a missao, num unico ponto.
`EvolutionDashboardService` minera o `git log` real (nunca uma lista de
missoes mantida a mao) para construir a linha do tempo, e agrega (nunca
recalcula) os tres motores existentes (`UnifiedCertificationEngine` da
Missao 53, `ArchitectureAuditService` da Missao 55, `CodeReviewService`
da Missao 56) para o snapshot de saude atual.

O que estes testes provam, na ordem: (1) `mission_timeline()` encontra de
fato os commits reais das Missoes 41-56 no historico deste repositorio,
incluindo as duas grafias (com e sem acento); (2) cada entrada tem os
campos esperados, vindos de `git show --stat`/diff reais, nao valores
fixos; (3) `timeline_health()` detecta lacuna e duplicata em dados
sinteticos injetados - nao e "passa hoje" disfarcado; (4)
`current_snapshot()` e um agregador puro dos tres motores (provado via
fakes monkeypatched nas proprias dependencias do service); (5)
`render_markdown()` produz texto coerente; (6) os endpoints HTTP novos
refletem o service real via o container de DI (Missao 52), nao um valor
hardcoded na propria rota; (7) ao contrario das Missoes 55/56,
`EvolutionDashboardService` PRECISA de `db` (porque
`UnifiedCertificationEngine` precisa) e por isso usa `provide()`, igual
`get_certification_service` (Missao 52) - confirmado que aparece em
`registered_providers()`.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.container import get_evolution_dashboard_service, registered_providers
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.evolution_dashboard_service import EvolutionDashboardService, _run_git


def _service() -> tuple[EvolutionDashboardService, "Session"]:
    db = SessionLocal()
    return EvolutionDashboardService(db), db


# --- _run_git: comando real, leitura pura -----------------------------------


def test_run_git_executes_against_the_real_project_repository():
    output = _run_git(["rev-parse", "--is-inside-work-tree"])
    assert output.strip() == "true"


def test_run_git_raises_visibly_on_an_invalid_subcommand():
    import subprocess

    import pytest

    with pytest.raises(subprocess.CalledProcessError):
        _run_git(["this-is-not-a-real-git-subcommand"])


# --- mission_timeline(): mineracao real do git log --------------------------


def test_mission_timeline_detects_the_real_historical_mission_commits():
    service, db = _service()
    try:
        timeline = service.mission_timeline()
        numbers = {entry["mission_number"] for entry in timeline}
        assert set(range(41, 57)).issubset(numbers)
    finally:
        db.close()


def test_mission_timeline_entries_have_the_expected_fields():
    service, db = _service()
    try:
        timeline = service.mission_timeline()
        assert timeline, "esperava ao menos uma missao detectada no historico real"
        entry = timeline[0]
        for field in (
            "mission_number",
            "commit_hash",
            "subject",
            "committed_at",
            "tests_added",
            "files_changed",
            "insertions",
            "deletions",
        ):
            assert field in entry
    finally:
        db.close()


def test_mission_timeline_is_sorted_ascending_by_mission_number():
    service, db = _service()
    try:
        timeline = service.mission_timeline()
        numbers = [entry["mission_number"] for entry in timeline]
        assert numbers == sorted(numbers)
    finally:
        db.close()


def test_mission_timeline_handles_both_accented_and_unaccented_subject_spelling():
    service, db = _service()
    try:
        timeline = service.mission_timeline()
        by_number = {entry["mission_number"]: entry for entry in timeline}
        # Missao 41 foi commitada com a grafia acentuada "Missão 41" e
        # Missao 42 com a grafia sem acento "Missao 42" - ambas devem ser
        # encontradas pelo mesmo regex tolerante a acento.
        assert 41 in by_number
        assert 42 in by_number
    finally:
        db.close()


def test_mission_timeline_stat_for_mission_56_matches_the_real_commit():
    # Missao 56 foi commitada com "4 files changed, 506 insertions(+)" -
    # valor real, conferido via `git show --stat` antes de escrever este
    # teste (nao um numero inventado).
    service, db = _service()
    try:
        timeline = service.mission_timeline()
        by_number = {entry["mission_number"]: entry for entry in timeline}
        entry_56 = by_number[56]
        assert entry_56["files_changed"] == 4
        assert entry_56["insertions"] == 506
        assert entry_56["deletions"] == 0
    finally:
        db.close()


def test_tests_added_counts_the_real_test_functions_for_mission_56():
    # test_m56_ai_code_reviewer.py foi um arquivo novo com 24 funcoes
    # test_ top-level - todas aparecem como linhas "+" no diff.
    service, db = _service()
    try:
        timeline = service.mission_timeline()
        by_number = {entry["mission_number"]: entry for entry in timeline}
        assert by_number[56]["tests_added"] == 24
    finally:
        db.close()


# --- timeline_health(): eixo informativo, lacunas e duplicatas -------------


def test_timeline_health_reports_no_gap_in_the_real_41_to_56_range():
    service, db = _service()
    try:
        health = service.timeline_health()
        missing = set(health["missing_mission_numbers"])
        assert missing.isdisjoint(range(41, 57))
    finally:
        db.close()


def test_timeline_health_reports_no_duplicate_in_the_real_history_today():
    service, db = _service()
    try:
        health = service.timeline_health()
        assert health["duplicate_mission_numbers"] == []
    finally:
        db.close()


def test_timeline_health_total_tests_added_matches_the_timeline_sum():
    service, db = _service()
    try:
        timeline = service.mission_timeline()
        health = service.timeline_health(timeline)
        expected = sum(entry["tests_added"] for entry in timeline)
        assert health["total_tests_added_across_missions"] == expected
    finally:
        db.close()


def test_timeline_health_detects_a_synthetic_gap_in_an_injected_timeline():
    service, db = _service()
    try:
        synthetic_timeline = [
            {"mission_number": 1, "tests_added": 0},
            {"mission_number": 2, "tests_added": 0},
            {"mission_number": 4, "tests_added": 0},
        ]
        health = service.timeline_health(synthetic_timeline)
        assert health["missing_mission_numbers"] == [3]
        assert health["lowest_mission_number"] == 1
        assert health["highest_mission_number"] == 4
    finally:
        db.close()


def test_timeline_health_detects_a_synthetic_duplicate_in_an_injected_timeline():
    service, db = _service()
    try:
        synthetic_timeline = [
            {"mission_number": 5, "tests_added": 0},
            {"mission_number": 5, "tests_added": 0},
            {"mission_number": 6, "tests_added": 0},
        ]
        health = service.timeline_health(synthetic_timeline)
        assert health["duplicate_mission_numbers"] == [5]
    finally:
        db.close()


def test_timeline_health_handles_an_empty_timeline_without_crashing():
    service, db = _service()
    try:
        health = service.timeline_health([])
        assert health["total_missions_detected"] == 0
        assert health["lowest_mission_number"] is None
        assert health["highest_mission_number"] is None
        assert health["missing_mission_numbers"] == []
        assert health["duplicate_mission_numbers"] == []
    finally:
        db.close()


# --- current_snapshot(): agregador puro, nunca recalcula --------------------


class _FakeUnifiedEngine:
    def certify(self):
        return {
            "unified_certified": False,
            "platinum_certified": False,
            "gold_certified": True,
        }


class _FakeArchitectureAudit:
    def audit(self):
        return {"clean": False}


class _FakeCodeReview:
    def review_repository(self):
        return {"clean": False, "total_blocking_findings": 3}


def test_current_snapshot_is_a_pure_aggregator_of_its_three_collaborators():
    service, db = _service()
    try:
        service.unified_engine = _FakeUnifiedEngine()
        service.architecture_audit = _FakeArchitectureAudit()
        service.code_review = _FakeCodeReview()

        snapshot = service.current_snapshot()
        assert snapshot["unified_certified"] is False
        assert snapshot["platinum_certified"] is False
        assert snapshot["gold_certified"] is True
        assert snapshot["architecture_clean"] is False
        assert snapshot["code_review_clean"] is False
        assert snapshot["code_review_blocking_findings"] == 3
    finally:
        db.close()


def test_current_snapshot_against_the_real_repository_returns_well_typed_fields():
    service, db = _service()
    try:
        snapshot = service.current_snapshot()
        assert isinstance(snapshot["unified_certified"], bool)
        assert isinstance(snapshot["architecture_clean"], bool)
        assert isinstance(snapshot["code_review_clean"], bool)
        assert isinstance(snapshot["code_review_blocking_findings"], int)
    finally:
        db.close()


# --- evolution_report() / render_markdown() ---------------------------------


def test_evolution_report_combines_timeline_and_snapshot():
    service, db = _service()
    try:
        report = service.evolution_report()
        assert "generated_at" in report
        assert "timeline" in report
        assert "timeline_health" in report
        assert "current_snapshot" in report
        assert report["timeline_health"]["total_missions_detected"] == len(report["timeline"])
    finally:
        db.close()


def test_render_markdown_mentions_the_real_mission_range():
    service, db = _service()
    try:
        markdown = service.render_markdown()
        assert "Evolution Dashboard" in markdown
        assert "Missao 41" in markdown or "Missao 42" in markdown
        assert "Missao 56" in markdown
    finally:
        db.close()


def test_render_markdown_reports_missing_numbers_when_present():
    service, db = _service()
    try:
        fake_report = {
            "generated_at": "2026-06-28T00:00:00+00:00",
            "timeline": [],
            "timeline_health": {
                "total_missions_detected": 2,
                "lowest_mission_number": 1,
                "highest_mission_number": 3,
                "missing_mission_numbers": [2],
                "duplicate_mission_numbers": [],
                "total_tests_added_across_missions": 0,
            },
            "current_snapshot": {
                "unified_certified": True,
                "platinum_certified": True,
                "gold_certified": True,
                "architecture_clean": True,
                "code_review_clean": True,
                "code_review_blocking_findings": 0,
            },
        }
        markdown = service.render_markdown(fake_report)
        assert "ausentes" in markdown
    finally:
        db.close()


# --- Container (Missao 52) e DI por rota -------------------------------------


def test_evolution_dashboard_service_is_registered_via_provide_unlike_m55_m56():
    # Diferente de ArchitectureAuditService/CodeReviewService (sem db),
    # EvolutionDashboardService precisa de db (UnifiedCertificationEngine
    # depende) - por isso usa provide(), igual get_certification_service.
    assert "EvolutionDashboardService" in registered_providers()


def test_evolution_dashboard_live_endpoint_returns_real_computed_report():
    client = TestClient(real_app)
    response = client.get("/api/v1/evolution-dashboard/live")
    assert response.status_code == 200
    payload = response.json()
    assert "timeline" in payload
    assert "timeline_health" in payload
    assert "current_snapshot" in payload


def test_evolution_dashboard_markdown_endpoint_returns_text():
    client = TestClient(real_app)
    response = client.get("/api/v1/evolution-dashboard/markdown")
    assert response.status_code == 200
    assert "Evolution Dashboard" in response.text


def test_evolution_dashboard_endpoint_is_overridable_via_container_not_hardcoded():
    class _FakeDashboard:
        def evolution_report(self):
            return {
                "generated_at": "2026-06-28T00:00:00+00:00",
                "timeline": [],
                "timeline_health": {
                    "total_missions_detected": 0,
                    "lowest_mission_number": None,
                    "highest_mission_number": None,
                    "missing_mission_numbers": [],
                    "duplicate_mission_numbers": [],
                    "total_tests_added_across_missions": 0,
                },
                "current_snapshot": {
                    "unified_certified": False,
                    "platinum_certified": False,
                    "gold_certified": False,
                    "architecture_clean": False,
                    "code_review_clean": False,
                    "code_review_blocking_findings": 9,
                },
            }

    real_app.dependency_overrides[get_evolution_dashboard_service] = lambda: _FakeDashboard()
    try:
        client = TestClient(real_app)
        response = client.get("/api/v1/evolution-dashboard/live")
        assert response.status_code == 200
        payload = response.json()
        assert payload["current_snapshot"]["code_review_blocking_findings"] == 9
    finally:
        real_app.dependency_overrides.pop(get_evolution_dashboard_service, None)
