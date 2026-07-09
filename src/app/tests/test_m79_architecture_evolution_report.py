"""Missao 79 - Architecture Evolution Report."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.architecture_evolution_service import ArchitectureEvolutionService


def test_evolution_report_shape():
    db = SessionLocal()
    try:
        report = ArchitectureEvolutionService(db).evolution_report()
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert "complexity_indicators" in report
        assert "refactoring_areas" in report
        assert "technical_recommendations" in report
    finally:
        db.close()


def test_recommendations_suppressed_when_disabled():
    db = SessionLocal()
    settings = get_settings()
    prev = settings.architecture_evolution_include_recommendations
    try:
        settings.architecture_evolution_include_recommendations = False
        report = ArchitectureEvolutionService(db).evolution_report()
        assert report["technical_recommendations"] == []
    finally:
        settings.architecture_evolution_include_recommendations = prev
        db.close()


def test_complexity_indicators_calculated():
    db = SessionLocal()
    try:
        report = ArchitectureEvolutionService(db).evolution_report()
        assert report["complexity_indicators"]["routes_loaded"] >= 1
    finally:
        db.close()


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/architecture-evolution/report/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    assert "# Architecture Evolution Report" in client.get("/api/v1/architecture-evolution/report/markdown").text


def test_config_2_8_0():
    assert tuple(int(x) for x in CONFIG_SCHEMA_VERSION.split(".")) >= (2, 8, 0)


def test_validate_settings_rejects_disabled_recommendations_in_production():
    settings = get_settings()
    prev = settings.architecture_evolution_include_recommendations
    try:
        settings.architecture_evolution_include_recommendations = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("architecture_evolution_include_recommendations" in i for i in issues)
    finally:
        settings.architecture_evolution_include_recommendations = prev
