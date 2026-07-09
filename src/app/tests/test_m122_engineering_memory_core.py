"""Missao 122 - Engineering Memory Core (Fase v2.1).

Cobertura desta suite: (1) `mission_history()` reusa
`EvolutionDashboardService.mission_timeline()` sem recalcular, provado via
fake injetado (nunca monkeypatch de modulo); (2)
`architectural_decision_history()` contra o repositorio real encontra os
arquivos reais de `docs/historico_missoes/`, com data de introducao vinda
do primeiro commit real (nao do mtime do disco), e devolve lista vazia com
elegancia quando o diretorio nao existe; (3) `incident_history()` delega
para `AlertService.history()` passando o `limit` adiante, sem reimplementar
nada; (4) `certification_history()` detecta mecanicamente, via caminho de
arquivo alterado no commit, contra timeline sintetica (prova a logica de
filtro) e contra o repositorio real (confirma que pelo menos as Missoes
53/55/56/60, que sabidamente tocam arquivos de certificacao/auditoria/
revisao, aparecem); (5) `version_history()` contra o `VERSION` real bate
com os commits conhecidos do historico do repositorio; (6)
`memory_report()` agrega as cinco fontes chamando a timeline uma unica vez;
(7) `trace()` - o criterio de aceite da missao ("qualquer decisao pode ser
rastreada") - acerta em cada uma das cinco fontes e nunca inventa
resultado para query vazia ou sem match; (8) registro via `provide()` e
endpoints HTTP refletindo o service real via container de DI (Missao 52),
nunca hardcoded na rota.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.container import get_engineering_memory_core_service, registered_providers
from app.core.config import project_root
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.engineering_memory_core_service import EngineeringMemoryCoreService

UTC = timezone.utc


def _service(**kwargs):
    db = SessionLocal()
    return EngineeringMemoryCoreService(db, **kwargs), db


# --- fakes --------------------------------------------------------------


class _FakeEvolutionDashboard:
    def __init__(self, timeline=None):
        self._timeline = timeline if timeline is not None else []
        self.timeline_calls = 0

    def mission_timeline(self):
        self.timeline_calls += 1
        return self._timeline


class _FakeAlertService:
    def __init__(self, events=None):
        self._events = events if events is not None else []
        self.history_calls = []

    def history(self, limit=None):
        self.history_calls.append(limit)
        return self._events


# --- 1. mission_history --------------------------------------------------


def test_mission_history_reuses_evolution_dashboard_timeline_without_recomputing():
    fake_dashboard = _FakeEvolutionDashboard(timeline=[{"mission_number": 57, "commit_hash": "abc1234", "subject": "Missao 57"}])
    service, db = _service(evolution_dashboard=fake_dashboard, alert_service=_FakeAlertService())
    try:
        result = service.mission_history()
        assert result == [{"mission_number": 57, "commit_hash": "abc1234", "subject": "Missao 57"}]
        assert fake_dashboard.timeline_calls == 1
    finally:
        db.close()


# --- 2. architectural_decision_history -----------------------------------


def test_architectural_decision_history_against_real_repository_finds_known_files():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        entries = service.architectural_decision_history()
        files = {entry["file"] for entry in entries}
        assert len(entries) >= 90
        assert "docs/historico_missoes/RELATORIO_MISSAO10_DECISION_FEED.md" in files
        for entry in entries:
            assert entry["file"].startswith("docs/historico_missoes/")
            assert entry["title"]
    finally:
        db.close()


def test_architectural_decision_history_entries_sorted_ascending_by_introduced_at():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        entries = service.architectural_decision_history()
        dated = [e["introduced_at"] for e in entries if e["introduced_at"] is not None]
        assert dated == sorted(dated)
    finally:
        db.close()


def test_architectural_decision_history_returns_empty_when_directory_missing(monkeypatch, tmp_path):
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        monkeypatch.setattr(
            "app.services.engineering_memory_core_service.project_root", lambda: tmp_path
        )
        assert service.architectural_decision_history() == []
    finally:
        db.close()


# --- 3. incident_history --------------------------------------------------


def test_incident_history_delegates_to_alert_service_with_limit():
    fake_alerts = _FakeAlertService(events=[{"check_name": "x", "message": "y"}])
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=fake_alerts)
    try:
        result = service.incident_history(limit=5)
        assert result == [{"check_name": "x", "message": "y"}]
        assert fake_alerts.history_calls == [5]
    finally:
        db.close()


def test_incident_history_default_limit_passes_none_through():
    fake_alerts = _FakeAlertService()
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=fake_alerts)
    try:
        service.incident_history()
        assert fake_alerts.history_calls == [None]
    finally:
        db.close()


# --- 4. certification_history --------------------------------------------


def test_certification_history_with_synthetic_timeline_and_fake_changed_paths(monkeypatch):
    fake_paths = {
        "aaa1111": ["src/app/services/code_review_service.py"],
        "bbb2222": ["src/app/services/unrelated_module.py"],
        "ccc3333": ["src/app/api/routes/enterprise_readiness.py"],
    }
    monkeypatch.setattr(
        EngineeringMemoryCoreService,
        "_changed_paths",
        staticmethod(lambda commit_hash: fake_paths.get(commit_hash, [])),
    )
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        timeline = [
            {"mission_number": 1, "commit_hash": "aaa1111", "subject": "Missao 1"},
            {"mission_number": 2, "commit_hash": "bbb2222", "subject": "Missao 2"},
            {"mission_number": 3, "commit_hash": "ccc3333", "subject": "Missao 3"},
        ]
        result = service.certification_history(timeline)
        assert [e["mission_number"] for e in result] == [1, 3]
        assert result[0]["certification_related_paths"] == ["src/app/services/code_review_service.py"]
    finally:
        db.close()


def test_certification_history_against_real_repository_detects_known_missions():
    service, db = _service(alert_service=_FakeAlertService())
    try:
        timeline = service.mission_history()
        result = service.certification_history(timeline)
        detected = {e["mission_number"] for e in result}
        assert {53, 55, 56, 60}.issubset(detected)
    finally:
        db.close()


# --- 5. version_history ---------------------------------------------------


def test_version_history_against_real_repository_matches_known_commits():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        entries = service.version_history()
        subjects = {e["subject"] for e in entries}
        expected_subjects = {
            "baseline: projeto automacao pre-github",
            "chore: package v1.0 release",
            "Registra fechamento oficial v1.0",
            "docs: complete omega certification reports",
        }
        assert expected_subjects.issubset(subjects)
        current_version = (project_root() / "VERSION").read_text().strip()
        assert entries[-1]["version"] == current_version
    finally:
        db.close()


def test_version_history_entries_sorted_ascending_by_committed_at():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        entries = service.version_history()
        timestamps = [e["committed_at"] for e in entries]
        assert timestamps == sorted(timestamps)
    finally:
        db.close()


# --- 6. memory_report ------------------------------------------------------


def test_memory_report_aggregates_all_five_histories_with_a_single_timeline_call():
    fake_dashboard = _FakeEvolutionDashboard(timeline=[])
    service, db = _service(evolution_dashboard=fake_dashboard, alert_service=_FakeAlertService())
    try:
        report = service.memory_report()
        assert set(report.keys()) == {
            "generated_at",
            "mission_history",
            "architectural_decision_history",
            "incident_history",
            "certification_history",
            "version_history",
        }
        assert fake_dashboard.timeline_calls == 1
    finally:
        db.close()


# --- 7. trace ---------------------------------------------------------------


def _synthetic_report():
    return {
        "mission_history": [{"mission_number": 57, "subject": "Missao 57 - Evolution Dashboard"}],
        "architectural_decision_history": [
            {"file": "docs/historico_missoes/RELATORIO_MISSAO10_DECISION_FEED.md", "title": "RELATORIO_MISSAO10_DECISION_FEED"}
        ],
        "incident_history": [{"check_name": "queue.unhealthy", "message": "fila travada"}],
        "certification_history": [
            {
                "mission_number": 60,
                "commit_hash": "504cd28",
                "subject": "Missao 60: Enterprise Readiness Certification",
                "certification_related_paths": ["src/app/services/enterprise_readiness_service.py"],
            }
        ],
        "version_history": [
            {
                "version": "1.1.0",
                "subject": "docs: complete omega certification reports",
                "committed_at": datetime(2026, 6, 28, tzinfo=UTC),
                "commit_hash": "feddd0f",
            }
        ],
    }


def test_trace_with_empty_query_returns_no_matches():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        result = service.trace("   ")
        assert result["matches"] == {}
        assert result["total_matches"] == 0
    finally:
        db.close()


def test_trace_matches_mission_history_by_subject():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        result = service.trace("evolution dashboard", report=_synthetic_report())
        assert len(result["matches"]["mission_history"]) == 1
    finally:
        db.close()


def test_trace_matches_architectural_decision_history_by_filename():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        result = service.trace("decision_feed", report=_synthetic_report())
        assert len(result["matches"]["architectural_decision_history"]) == 1
    finally:
        db.close()


def test_trace_matches_incident_history_by_check_name():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        result = service.trace("queue.unhealthy", report=_synthetic_report())
        assert len(result["matches"]["incident_history"]) == 1
    finally:
        db.close()


def test_trace_matches_certification_history_by_path():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        result = service.trace("enterprise_readiness_service", report=_synthetic_report())
        assert len(result["matches"]["certification_history"]) == 1
    finally:
        db.close()


def test_trace_matches_version_history_by_version_string():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        result = service.trace("1.1.0", report=_synthetic_report())
        assert len(result["matches"]["version_history"]) == 1
    finally:
        db.close()


def test_trace_total_matches_equals_sum_of_bucket_lengths():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        result = service.trace("missao 60", report=_synthetic_report())
        assert result["total_matches"] == sum(len(v) for v in result["matches"].values())
    finally:
        db.close()


def test_trace_with_no_match_returns_zero_across_all_five_buckets():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        result = service.trace("termo-que-nao-existe-em-lugar-nenhum-xyz", report=_synthetic_report())
        assert result["total_matches"] == 0
        assert all(len(v) == 0 for v in result["matches"].values())
    finally:
        db.close()


def test_trace_against_real_repository_does_not_crash():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        result = service.trace("Missao 57")
        assert result["query"] == "Missao 57"
        assert isinstance(result["total_matches"], int)
    finally:
        db.close()


# --- render_markdown ---------------------------------------------------


def test_render_markdown_includes_counts_and_version_timeline():
    report = _synthetic_report()
    report["generated_at"] = datetime.now(UTC)
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        markdown = service.render_markdown(report)
        assert "Engineering Memory Core (Missao 122)" in markdown
        assert "VERSION = 1.1.0" in markdown
        assert "Missao 60" in markdown
    finally:
        db.close()


def test_render_markdown_against_real_repository_does_not_crash():
    service, db = _service(evolution_dashboard=_FakeEvolutionDashboard(), alert_service=_FakeAlertService())
    try:
        markdown = service.render_markdown()
        assert markdown.startswith("# Engineering Memory Core (Missao 122)")
    finally:
        db.close()


# --- registro + endpoints HTTP -----------------------------------------


def test_engineering_memory_core_service_is_registered_via_provide():
    assert "EngineeringMemoryCoreService" in registered_providers()


def test_engineering_memory_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/engineering-memory/live")
        assert response.status_code == 200
        data = response.json()
        assert "mission_history" in data
        assert "architectural_decision_history" in data
        assert "incident_history" in data
        assert "certification_history" in data
        assert "version_history" in data


def test_engineering_memory_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/engineering-memory/markdown")
        assert response.status_code == 200
        assert "Engineering Memory Core" in response.text


def test_engineering_memory_trace_endpoint_returns_matches():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/engineering-memory/trace", params={"query": "Missao 57"})
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "Missao 57"
        assert "matches" in data


def test_engineering_memory_endpoint_is_overridable_via_container_not_hardcoded():
    class _StubMemory:
        def memory_report(self):
            return {"mission_history": "stub-marker"}

        def render_markdown(self, report=None):
            return "stub markdown"

        def trace(self, query, report=None):
            return {"query": query, "matches": {}, "total_matches": 0}

    real_app.dependency_overrides[get_engineering_memory_core_service] = lambda: _StubMemory()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/engineering-memory/live")
            assert response.json()["mission_history"] == "stub-marker"
    finally:
        real_app.dependency_overrides.pop(get_engineering_memory_core_service, None)
