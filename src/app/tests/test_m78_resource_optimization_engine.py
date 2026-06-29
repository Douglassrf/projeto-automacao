"""Missao 78 - Resource Optimization Engine."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.resource_optimization_service import ResourceOptimizationService


def test_optimization_report_shape():
    db = SessionLocal()
    try:
        report = ResourceOptimizationService(db).optimization_report()
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert "queue_optimization" in report
        assert "waste_reduction" in report
        assert "queue_health" in report
    finally:
        db.close()


def test_rebalance_disabled_returns_empty_recommendations():
    db = SessionLocal()
    settings = get_settings()
    prev = settings.resource_optimization_enable_rebalance
    try:
        settings.resource_optimization_enable_rebalance = False
        service = ResourceOptimizationService(db)
        recs = service._load_balance_recommendations({"per_queue": {"a": {"queued": 10}, "b": {"queued": 0}}})
        assert recs == []
    finally:
        settings.resource_optimization_enable_rebalance = prev
        db.close()


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/resource-optimization/engine/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    assert "# Resource Optimization Engine" in client.get("/api/v1/resource-optimization/engine/markdown").text


def test_config_2_7_0():
    assert tuple(int(x) for x in CONFIG_SCHEMA_VERSION.split(".")) >= (2, 7, 0)


def test_validate_settings_rejects_disabled_rebalance_in_production():
    settings = get_settings()
    prev = settings.resource_optimization_enable_rebalance
    try:
        settings.resource_optimization_enable_rebalance = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("resource_optimization_enable_rebalance" in i for i in issues)
    finally:
        settings.resource_optimization_enable_rebalance = prev
