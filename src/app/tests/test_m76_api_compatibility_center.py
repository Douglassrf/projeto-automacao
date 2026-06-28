"""Missao 76 - API Compatibility Center."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.api_compatibility_service import API_VERSION, ApiCompatibilityService


def test_compatibility_report_shape():
    db = SessionLocal()
    try:
        report = ApiCompatibilityService(db).compatibility_report()
        assert report["api_version"] == API_VERSION
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert "breaking_changes_registry" in report
        assert "deprecation_policy" in report
    finally:
        db.close()


def test_compatibility_tests_run():
    db = SessionLocal()
    try:
        report = ApiCompatibilityService(db).compatibility_report()
        assert len(report["compatibility_tests"]) >= 2
    finally:
        db.close()


def test_breaking_changes_suppressed_when_policy_disabled():
    db = SessionLocal()
    settings = get_settings()
    prev = settings.api_compatibility_enforce_deprecation_policy
    try:
        settings.api_compatibility_enforce_deprecation_policy = False
        report = ApiCompatibilityService(db).compatibility_report()
        assert report["breaking_changes_registry"] == []
    finally:
        settings.api_compatibility_enforce_deprecation_policy = prev
        db.close()


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/api-compatibility/center/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/api-compatibility/center/markdown")
    assert "# API Compatibility Center" in r.text


def test_config_2_5_0():
    assert tuple(int(x) for x in CONFIG_SCHEMA_VERSION.split(".")) >= (2, 5, 0)


def test_validate_settings_rejects_disabled_policy_in_production():
    settings = get_settings()
    prev = settings.api_compatibility_enforce_deprecation_policy
    try:
        settings.api_compatibility_enforce_deprecation_policy = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("api_compatibility_enforce_deprecation_policy" in i for i in issues)
    finally:
        settings.api_compatibility_enforce_deprecation_policy = prev
