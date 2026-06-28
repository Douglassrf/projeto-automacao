"""Missao 75 - Data Integrity Framework."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.data_integrity_service import STATUS_OK, DataIntegrityService


def test_integrity_report_shape():
    db = SessionLocal()
    try:
        report = DataIntegrityService(db).integrity_report()
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert report["overall_status"] in {"ok", "warning", "critical"}
        assert "backup_restore_integrity" in report
    finally:
        db.close()


def test_consistency_checks_include_database():
    db = SessionLocal()
    try:
        checks = DataIntegrityService(db)._consistency_checks()
        names = [c["name"] for c in checks]
        assert "database_roundtrip" in names
    finally:
        db.close()


def test_backup_restore_integrity_ok_on_sqlite():
    db = SessionLocal()
    try:
        backup = DataIntegrityService(db)._backup_restore_integrity()
        assert backup["healthy"] is True
    finally:
        db.close()


def test_strict_validation_flag_in_report():
    db = SessionLocal()
    try:
        report = DataIntegrityService(db).integrity_report()
        assert report["strict_validation"] is True
    finally:
        db.close()


def test_live_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/data-integrity/check/live")
    assert r.status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/data-integrity/check/markdown")
    assert r.status_code == 200
    assert "# Data Integrity Framework" in r.text


def test_config_2_4_0():
    assert tuple(int(x) for x in CONFIG_SCHEMA_VERSION.split(".")) >= (2, 4, 0)


def test_validate_settings_rejects_disabled_strict_in_production():
    settings = get_settings()
    prev = settings.data_integrity_strict_validation
    try:
        settings.data_integrity_strict_validation = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("data_integrity_strict_validation" in i for i in issues)
    finally:
        settings.data_integrity_strict_validation = prev
