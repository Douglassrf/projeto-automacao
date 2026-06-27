"""Missão 44 — Diagnóstico Automático.

Cobre: DiagnosticsService (check_database, check_queue, check_cache,
check_config, check_disk, run_full_diagnostics), os novos endpoints
GET /diagnostics/run e GET /diagnostics/checks/{name}, e as novas regras
de validate_settings()/CONFIG_SCHEMA_VERSION (Missão 44).

Os checks de queue/database/disk são testados via monkeypatch das
dependências (QueueService.health_report, Session.execute,
shutil.disk_usage) em vez de depender do estado real acumulado no banco
de desenvolvimento entre execuções de teste (o mesmo SQLite é reusado
entre sessões de pytest, então filas de missões anteriores podem deixar
dados residuais) - isola a lógica de mapeamento de severidade desta
missão do estado de outras suítes, seguindo o padrão de monkeypatch já
estabelecido em test_m02a_health.py.
"""

from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services import diagnostics_service as diagnostics_module
from app.services.diagnostics_service import (
    STATUS_CRITICAL,
    STATUS_OK,
    STATUS_WARNING,
    DiagnosticCheck,
    DiagnosticsService,
    UnknownDiagnosticCheckError,
)

# ---------------------------------------------------------------------------
# check_database()
# ---------------------------------------------------------------------------


def test_check_database_ok_on_healthy_connection():
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_database()
        assert result.status == STATUS_OK
        assert result.name == "database"
    finally:
        db.close()


def test_check_database_critical_when_execute_raises(monkeypatch):
    db = SessionLocal()
    try:
        def raiser(*args, **kwargs):
            raise SQLAlchemyError("boom")

        monkeypatch.setattr(db, "execute", raiser)
        result = DiagnosticsService(db).check_database()
        assert result.status == STATUS_CRITICAL
        assert result.details["error"] == "SQLAlchemyError"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# check_queue() - via monkeypatch de QueueService.health_report
# ---------------------------------------------------------------------------


def _fake_health_report(unhealthy=None, stuck=None, starving=None, warnings=None):
    return {
        "healthy": not (unhealthy or stuck or starving),
        "stuck_jobs": stuck or [],
        "starving_jobs": starving or [],
        "unhealthy_queues": unhealthy or [],
        "per_queue": {},
        "warnings": warnings or [],
    }


def test_check_queue_ok_when_health_report_is_clean(monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.QueueService, "health_report", lambda self: _fake_health_report()
    )
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_queue()
        assert result.status == STATUS_OK
    finally:
        db.close()


def test_check_queue_warning_when_stuck_jobs_present_but_no_unhealthy_queues(monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.QueueService,
        "health_report",
        lambda self: _fake_health_report(stuck=[{"id": 1}], warnings=["1 job travado"]),
    )
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_queue()
        assert result.status == STATUS_WARNING
        assert result.details["stuck_jobs_count"] == 1
    finally:
        db.close()


def test_check_queue_warning_when_starving_jobs_present_but_no_unhealthy_queues(monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.QueueService,
        "health_report",
        lambda self: _fake_health_report(starving=[{"id": 1}], warnings=["1 job em inanicao"]),
    )
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_queue()
        assert result.status == STATUS_WARNING
        assert result.details["starving_jobs_count"] == 1
    finally:
        db.close()


def test_check_queue_critical_when_unhealthy_queues_present(monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.QueueService,
        "health_report",
        lambda self: _fake_health_report(unhealthy=["q1"], warnings=["fila q1 com taxa de falha alta"]),
    )
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_queue()
        assert result.status == STATUS_CRITICAL
        assert result.details["unhealthy_queues"] == ["q1"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# check_cache() - sondagem funcional real (set + get + delete)
# ---------------------------------------------------------------------------


def test_check_cache_ok_on_successful_roundtrip():
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_cache()
        assert result.status == STATUS_OK
        assert result.details["roundtrip_ok"] is True
        assert "backend" in result.details
    finally:
        db.close()


def test_check_cache_critical_when_roundtrip_value_mismatches(monkeypatch):
    monkeypatch.setattr(
        diagnostics_module.CacheService, "get", lambda self, *a, **kw: {"unexpected": "value"}
    )
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_cache()
        assert result.status == STATUS_CRITICAL
        assert result.details["roundtrip_ok"] is False
    finally:
        db.close()


def test_check_cache_critical_when_set_raises(monkeypatch):
    def raiser(self, *a, **kw):
        raise RuntimeError("cache indisponivel")

    monkeypatch.setattr(diagnostics_module.CacheService, "set", raiser)
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_cache()
        assert result.status == STATUS_CRITICAL
        assert result.details["error"] == "RuntimeError"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# check_config() - delega a validate_settings()
# ---------------------------------------------------------------------------


def test_check_config_ok_when_no_problems(monkeypatch):
    monkeypatch.setattr(diagnostics_module, "detect_environment", lambda: Environment.DEVELOPMENT)
    monkeypatch.setattr(diagnostics_module, "validate_settings", lambda settings, env: [])
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_config()
        assert result.status == STATUS_OK
    finally:
        db.close()


def test_check_config_warning_in_development_with_problems(monkeypatch):
    monkeypatch.setattr(diagnostics_module, "detect_environment", lambda: Environment.DEVELOPMENT)
    monkeypatch.setattr(diagnostics_module, "validate_settings", lambda settings, env: ["problema x"])
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_config()
        assert result.status == STATUS_WARNING
        assert result.details["problems"] == ["problema x"]
    finally:
        db.close()


def test_check_config_critical_in_production_with_problems(monkeypatch):
    monkeypatch.setattr(diagnostics_module, "detect_environment", lambda: Environment.PRODUCTION)
    monkeypatch.setattr(diagnostics_module, "validate_settings", lambda settings, env: ["problema y"])
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_config()
        assert result.status == STATUS_CRITICAL
    finally:
        db.close()


def test_check_config_critical_in_testing_with_problems(monkeypatch):
    monkeypatch.setattr(diagnostics_module, "detect_environment", lambda: Environment.TESTING)
    monkeypatch.setattr(diagnostics_module, "validate_settings", lambda settings, env: ["problema z"])
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_config()
        assert result.status == STATUS_CRITICAL
    finally:
        db.close()


# ---------------------------------------------------------------------------
# check_disk() - via monkeypatch de shutil.disk_usage
# ---------------------------------------------------------------------------


class _FakeUsage:
    def __init__(self, total, used, free):
        self.total = total
        self.used = used
        self.free = free


def test_check_disk_ok_when_plenty_of_free_space(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(
        diagnostics_module.shutil,
        "disk_usage",
        lambda path: _FakeUsage(100_000 * 1024 * 1024, 1_000 * 1024 * 1024, 99_000 * 1024 * 1024),
    )
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_disk()
        assert result.status == STATUS_OK
        assert result.details["free_mb"] > settings.diagnostics_disk_warning_free_mb
    finally:
        db.close()


def test_check_disk_warning_when_free_space_below_warning_threshold(monkeypatch):
    settings = get_settings()
    free_mb = settings.diagnostics_disk_warning_free_mb - 1
    monkeypatch.setattr(
        diagnostics_module.shutil,
        "disk_usage",
        lambda path: _FakeUsage(10_000 * 1024 * 1024, 9_000 * 1024 * 1024, free_mb * 1024 * 1024),
    )
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_disk()
        assert result.status == STATUS_WARNING
    finally:
        db.close()


def test_check_disk_critical_when_free_space_below_critical_threshold(monkeypatch):
    settings = get_settings()
    free_mb = settings.diagnostics_disk_critical_free_mb - 1
    monkeypatch.setattr(
        diagnostics_module.shutil,
        "disk_usage",
        lambda path: _FakeUsage(10_000 * 1024 * 1024, 9_999 * 1024 * 1024, free_mb * 1024 * 1024),
    )
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_disk()
        assert result.status == STATUS_CRITICAL
    finally:
        db.close()


def test_check_disk_critical_when_path_is_invalid(monkeypatch):
    def raiser(path):
        raise OSError("path nao existe")

    monkeypatch.setattr(diagnostics_module.shutil, "disk_usage", raiser)
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).check_disk()
        assert result.status == STATUS_CRITICAL
        assert result.details["error"] == "OSError"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# run_full_diagnostics() - agregacao (pior status, contagens)
# ---------------------------------------------------------------------------


def _patch_all_checks(monkeypatch, service, statuses):
    for name, status in statuses.items():
        monkeypatch.setattr(
            service, f"check_{name}", lambda status=status, name=name: DiagnosticCheck(name, status, "msg", {})
        )


def test_run_full_diagnostics_overall_status_is_worst_of_all(monkeypatch):
    db = SessionLocal()
    try:
        service = DiagnosticsService(db)
        _patch_all_checks(
            monkeypatch,
            service,
            {"database": STATUS_OK, "queue": STATUS_WARNING, "cache": STATUS_OK, "config": STATUS_OK, "disk": STATUS_OK},
        )
        report = service.run_full_diagnostics()
        assert report["status"] == STATUS_WARNING
        assert report["summary"] == {STATUS_OK: 4, STATUS_WARNING: 1, STATUS_CRITICAL: 0}
        assert len(report["checks"]) == 5
    finally:
        db.close()


def test_run_full_diagnostics_critical_outranks_warning(monkeypatch):
    db = SessionLocal()
    try:
        service = DiagnosticsService(db)
        _patch_all_checks(
            monkeypatch,
            service,
            {"database": STATUS_CRITICAL, "queue": STATUS_WARNING, "cache": STATUS_OK, "config": STATUS_OK, "disk": STATUS_OK},
        )
        report = service.run_full_diagnostics()
        assert report["status"] == STATUS_CRITICAL
        assert report["summary"] == {STATUS_OK: 3, STATUS_WARNING: 1, STATUS_CRITICAL: 1}
    finally:
        db.close()


def test_run_full_diagnostics_all_ok_status_is_ok(monkeypatch):
    db = SessionLocal()
    try:
        service = DiagnosticsService(db)
        _patch_all_checks(
            monkeypatch,
            service,
            {"database": STATUS_OK, "queue": STATUS_OK, "cache": STATUS_OK, "config": STATUS_OK, "disk": STATUS_OK},
        )
        report = service.run_full_diagnostics()
        assert report["status"] == STATUS_OK
        assert report["summary"] == {STATUS_OK: 5, STATUS_WARNING: 0, STATUS_CRITICAL: 0}
        assert "generated_at" in report
    finally:
        db.close()


# ---------------------------------------------------------------------------
# run_check() - despacho por nome
# ---------------------------------------------------------------------------


def test_run_check_dispatches_to_named_check():
    db = SessionLocal()
    try:
        result = DiagnosticsService(db).run_check("database")
        assert result.name == "database"
    finally:
        db.close()


def test_run_check_raises_on_unknown_name():
    db = SessionLocal()
    try:
        try:
            DiagnosticsService(db).run_check("nao-existe")
            assert False, "deveria ter levantado UnknownDiagnosticCheckError"
        except UnknownDiagnosticCheckError as exc:
            assert "nao-existe" in str(exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API: GET /diagnostics/run, GET /diagnostics/checks/{name}
# ---------------------------------------------------------------------------


def test_run_diagnostics_endpoint_returns_expected_shape():
    with TestClient(app) as client:
        response = client.get("/api/v1/diagnostics/run")
        assert response.status_code == 200
        data = response.json()
        for key in ("status", "generated_at", "summary", "checks"):
            assert key in data
        assert len(data["checks"]) == 5
        names = {c["name"] for c in data["checks"]}
        assert names == {"database", "queue", "cache", "config", "disk"}


def test_run_single_check_endpoint_returns_expected_shape():
    with TestClient(app) as client:
        response = client.get("/api/v1/diagnostics/checks/database")
        assert response.status_code == 200
        data = response.json()
        for key in ("name", "status", "message", "details"):
            assert key in data
        assert data["name"] == "database"


def test_run_single_check_endpoint_404_on_unknown_name():
    with TestClient(app) as client:
        response = client.get("/api/v1/diagnostics/checks/nao-existe")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Config: schema version + novas regras de validacao (Missao 44)
# ---------------------------------------------------------------------------


def test_config_schema_version_bumped_for_mission_44():
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (1, 3, 0)


def test_validate_settings_rejects_disk_warning_threshold_below_one():
    settings = get_settings()
    previous = settings.diagnostics_disk_warning_free_mb
    try:
        settings.diagnostics_disk_warning_free_mb = 0
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("diagnostics_disk_warning_free_mb" in issue for issue in issues)
    finally:
        settings.diagnostics_disk_warning_free_mb = previous


def test_validate_settings_rejects_disk_critical_threshold_below_one():
    settings = get_settings()
    previous = settings.diagnostics_disk_critical_free_mb
    try:
        settings.diagnostics_disk_critical_free_mb = 0
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("diagnostics_disk_critical_free_mb" in issue for issue in issues)
    finally:
        settings.diagnostics_disk_critical_free_mb = previous


def test_validate_settings_rejects_critical_threshold_not_below_warning():
    settings = get_settings()
    previous_warning = settings.diagnostics_disk_warning_free_mb
    previous_critical = settings.diagnostics_disk_critical_free_mb
    try:
        settings.diagnostics_disk_warning_free_mb = 500
        settings.diagnostics_disk_critical_free_mb = 500
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("diagnostics_disk_critical_free_mb" in issue for issue in issues)
    finally:
        settings.diagnostics_disk_warning_free_mb = previous_warning
        settings.diagnostics_disk_critical_free_mb = previous_critical


def test_validate_settings_accepts_default_diagnostics_config():
    settings = get_settings()
    issues = validate_settings(settings, Environment.DEVELOPMENT)
    assert not any("diagnostics_disk" in issue for issue in issues)
