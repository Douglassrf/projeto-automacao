"""Missao 72 - Predictive Health Monitor.

Cobre: tendencias CPU/memoria/armazenamento, alertas preditivos,
relatorio de degradacao gradual, campo predictive_health_enable_predictive_alerts,
validate_settings(), CONFIG_SCHEMA_VERSION e endpoints /live + /markdown.
"""

from datetime import datetime

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.predictive_health_service import (
    TREND_DEGRADING,
    TREND_IMPROVING,
    TREND_STABLE,
    PredictiveHealthService,
    _compute_trend,
)


def test_monitor_report_returns_expected_top_level_shape():
    db = SessionLocal()
    try:
        report = PredictiveHealthService(db).monitor_report()
        expected_keys = {
            "generated_at",
            "environment",
            "config_schema_version",
            "predictive_alerts_enabled",
            "current_metrics",
            "trends",
            "metric_history",
            "predictive_alerts",
            "degradation_report",
            "config_validation_issues",
        }
        assert expected_keys <= set(report.keys())
        assert isinstance(report["generated_at"], datetime)
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
    finally:
        db.close()


def test_current_metrics_contains_cpu_memory_storage():
    db = SessionLocal()
    try:
        report = PredictiveHealthService(db).monitor_report()
        current = report["current_metrics"]
        assert "cpu_load_percent" in current
        assert "memory_used_percent" in current
        assert "storage_used_percent" in current
        assert "disk_free_mb" in current
        assert "managed_storage_mb" in current
    finally:
        db.close()


def test_metric_history_grows_on_repeated_calls():
    db = SessionLocal()
    try:
        service = PredictiveHealthService(db)
        first = service.monitor_report()
        second = service.monitor_report()
        assert len(second["metric_history"]) >= len(first["metric_history"])
        assert len(second["metric_history"]) >= 1
    finally:
        db.close()


def test_compute_trend_stable_for_small_delta():
    assert _compute_trend([10.0, 12.0]) == TREND_STABLE


def test_compute_trend_degrading_for_large_increase():
    assert _compute_trend([10.0, 20.0]) == TREND_DEGRADING


def test_compute_trend_improving_for_large_decrease():
    assert _compute_trend([50.0, 30.0]) == TREND_IMPROVING


def test_predictive_alerts_empty_when_flag_disabled():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.predictive_health_enable_predictive_alerts
    try:
        settings.predictive_health_enable_predictive_alerts = False
        service = PredictiveHealthService(db)
        alerts = service._predictive_alerts(
            trends={"cpu": TREND_DEGRADING, "memory": TREND_STABLE, "storage": TREND_STABLE},
            current={"disk_status": "ok"},
        )
        assert alerts == []
    finally:
        settings.predictive_health_enable_predictive_alerts = previous
        db.close()


def test_predictive_alerts_includes_degrading_cpu_when_enabled():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.predictive_health_enable_predictive_alerts
    try:
        settings.predictive_health_enable_predictive_alerts = True
        service = PredictiveHealthService(db)
        alerts = service._predictive_alerts(
            trends={"cpu": TREND_DEGRADING, "memory": TREND_STABLE, "storage": TREND_STABLE},
            current={"disk_status": "ok"},
        )
        assert any("CPU" in alert for alert in alerts)
    finally:
        settings.predictive_health_enable_predictive_alerts = previous
        db.close()


def test_degradation_report_flags_gradual_areas():
    db = SessionLocal()
    try:
        service = PredictiveHealthService(db)
        degradation = service._degradation_report(
            trends={"cpu": TREND_DEGRADING, "memory": TREND_STABLE, "storage": TREND_STABLE},
            history=[{}, {}],
            predictive_alerts=["alerta"],
        )
        assert "cpu" in degradation["gradual_degradation_areas"]
        assert degradation["snapshot_count"] == 2
    finally:
        db.close()


def test_render_markdown_contains_key_sections():
    db = SessionLocal()
    try:
        md = PredictiveHealthService(db).render_markdown()
        assert "# Predictive Health Monitor" in md
        assert "## Metricas atuais" in md
        assert "## Tendencias" in md
        assert "## Alertas preditivos" in md
        assert "## Degradacao gradual" in md
    finally:
        db.close()


def test_monitor_live_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.get("/api/v1/predictive-health/monitor/live")
    assert response.status_code == 200
    body = response.json()
    assert "current_metrics" in body
    assert "trends" in body
    assert "degradation_report" in body


def test_monitor_markdown_endpoint_returns_text_markdown():
    client = TestClient(app)
    response = client.get("/api/v1/predictive-health/monitor/markdown")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "# Predictive Health Monitor" in response.text


def test_config_schema_version_bumped_for_mission_72():
    current = tuple(int(part) for part in CONFIG_SCHEMA_VERSION.split("."))
    assert current >= (2, 1, 0)


def test_validate_settings_rejects_disabled_predictive_alerts_in_production():
    settings = get_settings()
    previous = settings.predictive_health_enable_predictive_alerts
    try:
        settings.predictive_health_enable_predictive_alerts = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("predictive_health_enable_predictive_alerts" in issue for issue in issues)
    finally:
        settings.predictive_health_enable_predictive_alerts = previous


def test_validate_settings_accepts_default_predictive_alerts_in_production():
    settings = get_settings()
    previous = settings.predictive_health_enable_predictive_alerts
    try:
        settings.predictive_health_enable_predictive_alerts = True
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert not any("predictive_health_enable_predictive_alerts" in issue for issue in issues)
    finally:
        settings.predictive_health_enable_predictive_alerts = previous
