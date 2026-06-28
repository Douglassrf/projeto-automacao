"""Missao 74 - Continuous Quality Gate."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.continuous_quality_service import ContinuousQualityService


def test_quality_report_shape():
    db = SessionLocal()
    try:
        report = ContinuousQualityService(db).quality_report()
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert "test_coverage" in report
        assert "technical_debt" in report
        assert "release_report" in report
    finally:
        db.close()


def test_test_coverage_counts_mission_files():
    db = SessionLocal()
    try:
        coverage = ContinuousQualityService(db)._test_coverage_indicators()
        assert coverage["mission_test_files"] >= 10
        assert coverage["total_test_files"] >= coverage["mission_test_files"]
    finally:
        db.close()


def test_technical_debt_uses_dependency_audit():
    db = SessionLocal()
    try:
        debt = ContinuousQualityService(db)._technical_debt_indicators()
        assert debt["unpinned_dependencies"] == 19
        assert debt["missing_dependencies"] == 0
    finally:
        db.close()


def test_release_gate_fails_when_standards_enforced_and_patterns_fail():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.quality_gate_enforce_standards
    try:
        settings.quality_gate_enforce_standards = True
        service = ContinuousQualityService(db)
        patterns = [{"status": "fail", "file": "x.py", "has_module_docstring": "True", "has_future_annotations": "False"}]
        release = service._release_report(
            coverage={"mission_test_files": 5},
            debt={"missing_dependencies": 0, "version_mismatches": 0},
            patterns=patterns,
        )
        assert release["gate_passed"] is False
    finally:
        settings.quality_gate_enforce_standards = previous
        db.close()


def test_render_markdown_sections():
    db = SessionLocal()
    try:
        md = ContinuousQualityService(db).render_markdown()
        assert "# Continuous Quality Gate" in md
        assert "## Cobertura de testes" in md
    finally:
        db.close()


def test_live_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/quality-gate/report/live")
    assert r.status_code == 200
    assert "release_report" in r.json()


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/quality-gate/report/markdown")
    assert r.status_code == 200
    assert "# Continuous Quality Gate" in r.text


def test_config_version_2_3_0():
    assert tuple(int(x) for x in CONFIG_SCHEMA_VERSION.split(".")) >= (2, 3, 0)


def test_validate_settings_rejects_disabled_standards_in_production():
    settings = get_settings()
    prev = settings.quality_gate_enforce_standards
    try:
        settings.quality_gate_enforce_standards = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("quality_gate_enforce_standards" in i for i in issues)
    finally:
        settings.quality_gate_enforce_standards = prev
