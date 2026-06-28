"""Missao 125 - Predictive Maintenance Center (Fase v2.1).

Cobertura desta suite: (1) `component_inventory()` deriva
`age_days`/`days_since_last_change`/`activity` corretamente a partir de
campos reais de entrada (`first_commit`/`last_commit`/`total_commits`),
incluindo os limiares exatos de `_STALE_AFTER_DAYS` (90) e
`_DORMANT_AFTER_DAYS` (365); (2) `change_trends()` agrega por grupo
sem perder nenhum arquivo do inventario; (3) `preventive_alerts()`
respeita o limiar de recorrencia (`_RECURRING_INCIDENT_THRESHOLD = 2`)
e exclui explicitamente qualquer `check_name` ja ativo; (4)
`aging_components()` filtra/ordena/recorta sem alterar os dados; (5)
`replacement_suggestions()` so sugere arquivos com os DOIS sinais
(envelhecido + divida conhecida) ao mesmo tempo, com normalizacao
correta de caminho entre o formato da Missao 58 (relativo a
`src/app/`) e o da Missao 123 (relativo a raiz do repo); (6) reuso
DIRETO comprovado via fakes com contador de chamadas - nenhum destes
servicos remina o `git` por conta propria; (7) `render_markdown()`
nos dois ramos (com e sem achados); (8) smoke test contra o
repositorio real (rapido - nenhuma destas fontes usa
ArchitectureStressTestService/TestClient, diferente da Missao 124);
(9) registro via `provide()` e endpoints HTTP refletindo o service real
via container de DI (Missao 52)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.container import get_predictive_maintenance_service, registered_providers
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.predictive_maintenance_service import PredictiveMaintenanceService

UTC = timezone.utc
NOW = datetime.now(UTC)


def _service(**kwargs):
    db = SessionLocal()
    return PredictiveMaintenanceService(db, **kwargs), db


def _commit(days_ago: int, subject: str = "c"):
    return {
        "commit_hash": "abc1234",
        "committed_at": NOW - timedelta(days=days_ago),
        "subject": subject,
    }


def _file_entry(file: str, first_days_ago: int, last_days_ago: int, total_commits: int):
    return {
        "file": file,
        "first_commit": _commit(first_days_ago, "primeiro"),
        "last_commit": _commit(last_days_ago, "ultimo"),
        "total_commits": total_commits,
    }


# --- fakes (contador de chamadas comprova reuso direto, nunca remineracao) --


class _FakeEvolutionTimeline:
    def __init__(self, module_files=None, api_files=None, service_files=None):
        self._module_files = module_files if module_files is not None else []
        self._api_files = api_files if api_files is not None else []
        self._service_files = service_files if service_files is not None else []
        self.module_evolution_calls = 0
        self.api_evolution_calls = 0
        self.service_evolution_calls = 0

    def module_evolution(self):
        self.module_evolution_calls += 1
        return {"files": self._module_files, "files_without_history": []}

    def api_evolution(self):
        self.api_evolution_calls += 1
        return {"files": self._api_files, "files_without_history": []}

    def service_evolution(self):
        self.service_evolution_calls += 1
        return {"files": self._service_files, "files_without_history": []}


class _FakeAlertService:
    def __init__(self, history=None, active=None):
        self._history = history if history is not None else []
        self._active = active if active is not None else []
        self.history_calls = 0
        self.active_alerts_calls = 0

    def history(self, limit=None):
        self.history_calls += 1
        return self._history

    def active_alerts(self):
        self.active_alerts_calls += 1
        return self._active


def _alert_event(check_name, seen_days_ago, message="falhou"):
    return {
        "check_name": check_name,
        "message": message,
        "first_seen_at": NOW - timedelta(days=seen_days_ago),
    }


# --- component_inventory(): classificacao de atividade ----------------------


def test_component_inventory_classifies_active_below_stale_threshold():
    fake_timeline = _FakeEvolutionTimeline(
        service_files=[_file_entry("src/app/services/x.py", first_days_ago=200, last_days_ago=10, total_commits=5)]
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        inventory = service.component_inventory()
        assert len(inventory) == 1
        entry = inventory[0]
        assert entry["activity"] == "active"
        assert entry["days_since_last_change"] == 10
        assert entry["age_days"] == 200
        assert entry["total_commits"] == 5
        assert entry["component_group"] == "service"
    finally:
        db.close()


def test_component_inventory_classifies_aging_at_exact_stale_threshold():
    fake_timeline = _FakeEvolutionTimeline(
        module_files=[_file_entry("src/app/core/y.py", first_days_ago=500, last_days_ago=90, total_commits=3)]
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        entry = service.component_inventory()[0]
        assert entry["activity"] == "aging"
        assert entry["days_since_last_change"] == 90
    finally:
        db.close()


def test_component_inventory_classifies_dormant_at_exact_dormant_threshold():
    fake_timeline = _FakeEvolutionTimeline(
        api_files=[_file_entry("src/app/api/routes/z.py", first_days_ago=900, last_days_ago=365, total_commits=2)]
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        entry = service.component_inventory()[0]
        assert entry["activity"] == "dormant"
    finally:
        db.close()


def test_component_inventory_one_day_before_dormant_threshold_is_still_aging():
    fake_timeline = _FakeEvolutionTimeline(
        service_files=[_file_entry("src/app/services/w.py", first_days_ago=900, last_days_ago=364, total_commits=2)]
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        entry = service.component_inventory()[0]
        assert entry["activity"] == "aging"
    finally:
        db.close()


def test_component_inventory_reuses_all_three_evolution_methods_exactly_once():
    fake_timeline = _FakeEvolutionTimeline()
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        service.component_inventory()
        assert fake_timeline.module_evolution_calls == 1
        assert fake_timeline.api_evolution_calls == 1
        assert fake_timeline.service_evolution_calls == 1
    finally:
        db.close()


def test_component_inventory_sorted_by_days_since_last_change_descending():
    fake_timeline = _FakeEvolutionTimeline(
        service_files=[
            _file_entry("src/app/services/recent.py", first_days_ago=100, last_days_ago=5, total_commits=1),
            _file_entry("src/app/services/old.py", first_days_ago=500, last_days_ago=400, total_commits=1),
        ]
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        files = [e["file"] for e in service.component_inventory()]
        assert files == ["src/app/services/old.py", "src/app/services/recent.py"]
    finally:
        db.close()


# --- change_trends() ---------------------------------------------------------


def test_change_trends_aggregates_activity_counts_per_group_without_losing_files():
    fake_timeline = _FakeEvolutionTimeline(
        module_files=[_file_entry("src/app/core/a.py", 200, 10, 4)],
        api_files=[
            _file_entry("src/app/api/routes/b.py", 500, 100, 2),
            _file_entry("src/app/api/routes/c.py", 500, 400, 2),
        ],
        service_files=[],
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        trends = service.change_trends()
        assert trends["total_tracked_files"] == 3
        assert trends["by_group"]["module"]["tracked_files"] == 1
        assert trends["by_group"]["module"]["activity_counts"] == {"active": 1, "aging": 0, "dormant": 0}
        assert trends["by_group"]["api"]["tracked_files"] == 2
        assert trends["by_group"]["api"]["activity_counts"] == {"active": 0, "aging": 1, "dormant": 1}
        assert trends["by_group"]["service"]["tracked_files"] == 0
        assert trends["by_group"]["service"]["average_commits_per_day"] == 0.0
    finally:
        db.close()


# --- preventive_alerts() -----------------------------------------------------


def test_preventive_alerts_flags_check_with_two_or_more_past_episodes():
    history = [_alert_event("queue_health", 30), _alert_event("queue_health", 10)]
    fake_alerts = _FakeAlertService(history=history, active=[])
    service, db = _service(alert_service=fake_alerts)
    try:
        report = service.preventive_alerts()
        names = [e["check_name"] for e in report["preventive_watchlist"]]
        assert names == ["queue_health"]
        assert report["preventive_watchlist"][0]["historical_episode_count"] == 2
    finally:
        db.close()


def test_preventive_alerts_ignores_check_with_single_past_episode():
    history = [_alert_event("disk_space", 30)]
    fake_alerts = _FakeAlertService(history=history, active=[])
    service, db = _service(alert_service=fake_alerts)
    try:
        report = service.preventive_alerts()
        assert report["preventive_watchlist"] == []
        assert report["checks_with_history"] == 1
    finally:
        db.close()


def test_preventive_alerts_excludes_check_that_is_currently_active():
    history = [_alert_event("cache_health", 30), _alert_event("cache_health", 5)]
    fake_alerts = _FakeAlertService(
        history=history,
        active=[{"check_name": "cache_health", "severity": "critical", "message": "m", "status": "open"}],
    )
    service, db = _service(alert_service=fake_alerts)
    try:
        report = service.preventive_alerts()
        assert report["preventive_watchlist"] == []
        assert report["currently_active_check_count"] == 1
    finally:
        db.close()


def test_preventive_alerts_reuses_history_and_active_alerts_exactly_once():
    fake_alerts = _FakeAlertService()
    service, db = _service(alert_service=fake_alerts)
    try:
        service.preventive_alerts()
        assert fake_alerts.history_calls == 1
        assert fake_alerts.active_alerts_calls == 1
    finally:
        db.close()


# --- aging_components() ------------------------------------------------------


def test_aging_components_filters_out_active_files():
    fake_timeline = _FakeEvolutionTimeline(
        service_files=[
            _file_entry("src/app/services/active.py", 100, 5, 1),
            _file_entry("src/app/services/aging.py", 500, 95, 1),
            _file_entry("src/app/services/dormant.py", 900, 400, 1),
        ]
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        report = service.aging_components()
        files = [e["file"] for e in report["top"]]
        assert files == ["src/app/services/dormant.py", "src/app/services/aging.py"]
        assert report["aging_component_count"] == 2
    finally:
        db.close()


def test_aging_components_respects_top_n():
    fake_timeline = _FakeEvolutionTimeline(
        service_files=[
            _file_entry(f"src/app/services/f{i}.py", 500, 100 + i, 1) for i in range(5)
        ]
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        report = service.aging_components(top_n=2)
        assert len(report["top"]) == 2
        assert report["aging_component_count"] == 5
    finally:
        db.close()


# --- replacement_suggestions() ----------------------------------------------


class _FakeTechDebtManagerForSuggestions:
    """Substitui o `TechDebtManagerService()` instanciado internamente por
    `_debt_file_set()` - usado via monkeypatch direto no metodo estatico
    para provar a normalizacao de caminho sem depender do repositorio
    real."""


def test_replacement_suggestions_requires_both_aging_and_known_debt(monkeypatch):
    fake_timeline = _FakeEvolutionTimeline(
        service_files=[
            _file_entry("src/app/services/aging_with_debt.py", 500, 200, 1),
            _file_entry("src/app/services/aging_no_debt.py", 500, 200, 1),
            _file_entry("src/app/services/recent_with_debt.py", 100, 5, 1),
        ]
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        monkeypatch.setattr(
            PredictiveMaintenanceService,
            "_debt_file_set",
            staticmethod(
                lambda: (
                    {"src/app/services/aging_with_debt.py", "src/app/services/recent_with_debt.py"},
                    {"src/app/services/aging_with_debt.py": 42, "src/app/services/recent_with_debt.py": 7},
                )
            ),
        )
        report = service.replacement_suggestions()
        files = [e["file"] for e in report["top"]]
        assert files == ["src/app/services/aging_with_debt.py"]
        assert report["top"][0]["known_debt_score"] == 42
    finally:
        db.close()


def test_replacement_suggestions_empty_when_no_overlap(monkeypatch):
    fake_timeline = _FakeEvolutionTimeline(
        service_files=[_file_entry("src/app/services/aging_only.py", 500, 200, 1)]
    )
    service, db = _service(evolution_timeline=fake_timeline)
    try:
        monkeypatch.setattr(
            PredictiveMaintenanceService,
            "_debt_file_set",
            staticmethod(lambda: (set(), {})),
        )
        report = service.replacement_suggestions()
        assert report["top"] == []
        assert report["suggestion_count"] == 0
    finally:
        db.close()


def test_debt_file_set_normalizes_paths_to_src_app_prefix_from_real_tech_debt_manager():
    """Nao usa fake aqui de proposito: prova que a normalizacao de
    caminho (`src/app/<resto>` <- `<resto>` relativo a `src/app/`) bate
    com o formato real que `TechDebtManagerService.debt_report()`
    (Missao 58) devolve hoje no repositorio."""
    service, db = _service()
    try:
        debt_files, debt_scores = service._debt_file_set()
        for file in debt_files:
            assert file.startswith("src/app/")
            assert "src/app/src/app/" not in file
    finally:
        db.close()


# --- render_markdown() -------------------------------------------------------


def test_render_markdown_shows_no_findings_message_when_everything_is_clean():
    fake_timeline = _FakeEvolutionTimeline()
    fake_alerts = _FakeAlertService()
    service, db = _service(evolution_timeline=fake_timeline, alert_service=fake_alerts)
    try:
        text = service.render_markdown()
        assert "Nenhum check recorrente fora dos ja ativos agora." in text
        assert "Nenhum arquivo atende aos dois criterios ao mesmo tempo hoje." in text
        assert "Centro de Manutencao Preditiva (Missao 125)" in text
    finally:
        db.close()


def test_render_markdown_lists_watchlist_and_suggestions_when_present(monkeypatch):
    fake_timeline = _FakeEvolutionTimeline(
        service_files=[_file_entry("src/app/services/old.py", 500, 200, 3)]
    )
    fake_alerts = _FakeAlertService(history=[_alert_event("queue_health", 30), _alert_event("queue_health", 5)])
    service, db = _service(evolution_timeline=fake_timeline, alert_service=fake_alerts)
    try:
        monkeypatch.setattr(
            PredictiveMaintenanceService,
            "_debt_file_set",
            staticmethod(lambda: ({"src/app/services/old.py"}, {"src/app/services/old.py": 9})),
        )
        text = service.render_markdown()
        assert "queue_health" in text
        assert "src/app/services/old.py" in text
    finally:
        db.close()


# --- smoke test contra o repositorio real (rapido) ---------------------------


def test_maintenance_report_against_real_repository_has_well_typed_fields():
    service, db = _service()
    try:
        report = service.maintenance_report()
        assert isinstance(report["trends"]["total_tracked_files"], int)
        assert isinstance(report["preventive_alerts"]["preventive_watchlist"], list)
        assert isinstance(report["aging_components"]["aging_component_count"], int)
        assert isinstance(report["replacement_suggestions"]["suggestion_count"], int)
        markdown = service.render_markdown(report)
        assert "Missao 125" in markdown
    finally:
        db.close()


# --- registro e HTTP ---------------------------------------------------------


def test_predictive_maintenance_service_is_registered_via_provide():
    assert "PredictiveMaintenanceService" in registered_providers()


def test_predictive_maintenance_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/predictive-maintenance/live")
    assert response.status_code == 200
    body = response.json()
    assert "trends" in body
    assert "replacement_suggestions" in body


def test_predictive_maintenance_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/predictive-maintenance/markdown")
    assert response.status_code == 200
    assert "Centro de Manutencao Preditiva" in response.text


def test_predictive_maintenance_endpoint_is_overridable_via_container_not_hardcoded():
    class _StubMaintenance:
        def maintenance_report(self):
            return {"stub": True}

    real_app.dependency_overrides[get_predictive_maintenance_service] = lambda: _StubMaintenance()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/predictive-maintenance/live")
        assert response.json() == {"stub": True}
    finally:
        real_app.dependency_overrides.pop(get_predictive_maintenance_service, None)
