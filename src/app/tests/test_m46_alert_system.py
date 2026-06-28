"""Missao 46 - Sistema de Alertas.

Contraparte com ESTADO da Missao 44 (Diagnostico Automatico, snapshot sem
persistencia): aqui, um check que reporta warning/critical abre um
AlertEvent que permanece "open" enquanto o problema persistir, e e
marcado "resolved" quando o check correspondente volta a "ok".

Os testes de AlertService.evaluate() substituem
DiagnosticsService.run_full_diagnostics() por um relatorio sintetico (via
monkeypatch), usando um nome de check unico por teste (uuid) - o mesmo
problema de estado compartilhado documentado nas Missoes 44/45 (o banco
de dev/teste e reusado entre sessoes de pytest) torna necessario isolar
cada teste do estado de checks reais e de outras execucoes.

Cobre: AlertEvent (modelo), AlertService.evaluate() (abrir/atualizar/
resolver + de-duplicacao), active_alerts(), history() (incluindo o limite
default vindo de settings.alert_history_default_limit), os novos
endpoints /system-alerts/* e as novas regras de
validate_settings()/CONFIG_SCHEMA_VERSION (Missao 46).
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.domain.models import AlertEvent
from app.main import app
from app.services.alert_service import ALERT_STATUS_OPEN, ALERT_STATUS_RESOLVED, AlertService
from app.services.diagnostics_service import STATUS_CRITICAL, STATUS_OK, STATUS_WARNING

UTC = timezone.utc


def _check_name() -> str:
    return f"m46-check-{uuid4().hex[:8]}"


def _report(checks: list[tuple[str, str, str]]) -> dict:
    """Constroi um relatorio no mesmo formato de
    DiagnosticsService.run_full_diagnostics(), a partir de uma lista de
    (name, status, message)."""
    statuses = [status for _, status, _ in checks]
    overall = STATUS_OK
    if STATUS_CRITICAL in statuses:
        overall = STATUS_CRITICAL
    elif STATUS_WARNING in statuses:
        overall = STATUS_WARNING
    return {
        "status": overall,
        "generated_at": datetime.now(UTC),
        "summary": {
            STATUS_OK: sum(1 for s in statuses if s == STATUS_OK),
            STATUS_WARNING: sum(1 for s in statuses if s == STATUS_WARNING),
            STATUS_CRITICAL: sum(1 for s in statuses if s == STATUS_CRITICAL),
        },
        "checks": [
            {"name": name, "status": status, "message": message, "details": {}}
            for name, status, message in checks
        ],
    }


def _open_events(db, check_name: str) -> list[AlertEvent]:
    return (
        db.query(AlertEvent)
        .filter(AlertEvent.check_name == check_name, AlertEvent.status == ALERT_STATUS_OPEN)
        .all()
    )


# ---------------------------------------------------------------------------
# evaluate() - abrir
# ---------------------------------------------------------------------------


def test_evaluate_opens_new_alert_for_failing_check(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_CRITICAL, "falhou")])
        )
        result = service.evaluate()
        assert name in result["opened"]
        rows = _open_events(db, name)
        assert len(rows) == 1
        assert rows[0].severity == STATUS_CRITICAL
        assert rows[0].message == "falhou"
        assert rows[0].status == ALERT_STATUS_OPEN
    finally:
        db.close()


def test_evaluate_does_not_open_alert_for_ok_check(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_OK, "tudo bem")])
        )
        result = service.evaluate()
        assert result["opened"] == []
        assert _open_events(db, name) == []
    finally:
        db.close()


# ---------------------------------------------------------------------------
# evaluate() - de-duplicacao / atualizacao
# ---------------------------------------------------------------------------


def test_evaluate_does_not_duplicate_open_alert_on_repeated_failure(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_WARNING, "ainda ruim")])
        )
        service.evaluate()
        second = service.evaluate()

        assert name in second["updated"]
        assert name not in second["opened"]
        assert len(_open_events(db, name)) == 1
    finally:
        db.close()


def test_evaluate_updates_severity_and_message_on_existing_open_alert(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_WARNING, "leve")])
        )
        service.evaluate()
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_CRITICAL, "piorou")])
        )
        service.evaluate()

        rows = _open_events(db, name)
        assert len(rows) == 1
        assert rows[0].severity == STATUS_CRITICAL
        assert rows[0].message == "piorou"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# evaluate() - resolver
# ---------------------------------------------------------------------------


def test_evaluate_resolves_alert_when_check_recovers(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_CRITICAL, "caiu")])
        )
        service.evaluate()
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_OK, "recuperou")])
        )
        second = service.evaluate()

        assert name in second["resolved"]
        assert _open_events(db, name) == []
        resolved_row = (
            db.query(AlertEvent)
            .filter(AlertEvent.check_name == name, AlertEvent.status == ALERT_STATUS_RESOLVED)
            .first()
        )
        assert resolved_row is not None
        assert resolved_row.resolved_at is not None
    finally:
        db.close()


def test_evaluate_recovering_ok_with_no_open_alert_is_a_noop(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_OK, "sempre bem")])
        )
        result = service.evaluate()
        assert result["resolved"] == []
    finally:
        db.close()


def test_evaluate_reopens_a_new_event_after_resolution_if_it_fails_again(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_CRITICAL, "caiu 1")])
        )
        service.evaluate()
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_OK, "ok")])
        )
        service.evaluate()
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_CRITICAL, "caiu 2")])
        )
        third = service.evaluate()

        assert name in third["opened"]
        rows = _open_events(db, name)
        assert len(rows) == 1
        assert rows[0].message == "caiu 2"
        # historico mantem as duas linhas (resolvida + a nova aberta), nao
        # sobrescreve a antiga.
        all_rows = db.query(AlertEvent).filter(AlertEvent.check_name == name).all()
        assert len(all_rows) == 2
    finally:
        db.close()


def test_evaluate_returns_overall_status_from_report(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_CRITICAL, "x")])
        )
        result = service.evaluate()
        assert result["overall_status"] == STATUS_CRITICAL
    finally:
        db.close()


# ---------------------------------------------------------------------------
# active_alerts() / history()
# ---------------------------------------------------------------------------


def test_active_alerts_excludes_resolved(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_WARNING, "x")])
        )
        service.evaluate()
        active_names = {a["check_name"] for a in service.active_alerts()}
        assert name in active_names

        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_OK, "ok")])
        )
        service.evaluate()
        active_names_after = {a["check_name"] for a in service.active_alerts()}
        assert name not in active_names_after
    finally:
        db.close()


def test_active_alerts_entry_shape(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_WARNING, "x")])
        )
        service.evaluate()
        entry = next(a for a in service.active_alerts() if a["check_name"] == name)
        assert set(entry.keys()) == {
            "id",
            "check_name",
            "severity",
            "message",
            "status",
            "first_seen_at",
            "last_seen_at",
            "resolved_at",
        }
    finally:
        db.close()


def test_history_includes_resolved_and_open(monkeypatch):
    db = SessionLocal()
    try:
        name = _check_name()
        service = AlertService(db)
        monkeypatch.setattr(
            service.diagnostics, "run_full_diagnostics", lambda: _report([(name, STATUS_CRITICAL, "x")])
        )
        service.evaluate()
        history_names = {h["check_name"] for h in service.history(limit=1000)}
        assert name in history_names
    finally:
        db.close()


def test_history_respects_explicit_limit():
    db = SessionLocal()
    try:
        prefix = uuid4().hex[:8]
        for i in range(5):
            db.add(AlertEvent(check_name=f"m46-hist-{prefix}-{i}", severity=STATUS_WARNING, message="x"))
        db.commit()
        service = AlertService(db)
        result = service.history(limit=2)
        assert len(result) == 2
    finally:
        db.close()


def test_history_uses_settings_default_limit_when_not_specified():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.alert_history_default_limit
    try:
        settings.alert_history_default_limit = 3
        prefix = uuid4().hex[:8]
        for i in range(6):
            db.add(AlertEvent(check_name=f"m46-histdef-{prefix}-{i}", severity=STATUS_WARNING, message="x"))
        db.commit()
        service = AlertService(db)
        result = service.history()
        assert len(result) == 3
    finally:
        settings.alert_history_default_limit = previous
        db.close()


def test_history_orders_most_recent_first():
    db = SessionLocal()
    try:
        prefix = uuid4().hex[:8]
        names = [f"m46-order-{prefix}-{i}" for i in range(3)]
        for name in names:
            db.add(AlertEvent(check_name=name, severity=STATUS_WARNING, message="x"))
            db.commit()
        service = AlertService(db)
        result = [h["check_name"] for h in service.history(limit=3) if h["check_name"] in names]
        assert result == list(reversed(names))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API: /system-alerts/*
# ---------------------------------------------------------------------------


def test_evaluate_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.post("/api/v1/system-alerts/evaluate")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"overall_status", "evaluated_at", "opened", "updated", "resolved"}


def test_active_endpoint_returns_a_list():
    client = TestClient(app)
    response = client.get("/api/v1/system-alerts/active")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_history_endpoint_returns_a_list():
    client = TestClient(app)
    response = client.get("/api/v1/system-alerts/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_history_endpoint_accepts_limit_query_param():
    client = TestClient(app)
    response = client.get("/api/v1/system-alerts/history", params={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()) <= 2


def test_history_endpoint_rejects_limit_below_one():
    client = TestClient(app)
    response = client.get("/api/v1/system-alerts/history", params={"limit": 0})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Configuracao - versionamento e validacao (Missao 46)
# ---------------------------------------------------------------------------


def test_config_schema_version_bumped_for_mission_46():
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (1, 5, 0)


def test_validate_settings_rejects_alert_history_limit_below_one():
    settings = get_settings()
    previous = settings.alert_history_default_limit
    try:
        settings.alert_history_default_limit = 0
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("alert_history_default_limit" in issue for issue in issues)
    finally:
        settings.alert_history_default_limit = previous


def test_validate_settings_accepts_default_alert_config():
    settings = get_settings()
    issues = validate_settings(settings, Environment.DEVELOPMENT)
    assert not any("alert_history_default_limit" in issue for issue in issues)
