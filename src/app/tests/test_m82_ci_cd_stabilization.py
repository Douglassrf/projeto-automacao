"""Missao 82 - CI/CD Stabilization."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.main import app
from app.services.ci_stabilization_service import (
    FLAKY_TESTS_TRACKED,
    VERDICT_NOT_READY,
    VERDICT_READY,
    CiStabilizationService,
)


def test_stabilization_report_shape():
    report = CiStabilizationService().stabilization_report()
    assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
    parts = tuple(int(p) for p in report["config_schema_version"].split("."))
    assert parts >= (3, 1, 0)
    assert "verdict" in report
    assert "workflow_files" in report
    assert "ci.yml" in report["workflow_files"]


def test_flaky_tests_tracked():
    assert len(FLAKY_TESTS_TRACKED) >= 3


def test_verdict_not_ready_when_gate_disabled():
    settings = get_settings()
    prev = settings.ci_cd_require_green_pipeline
    try:
        settings.ci_cd_require_green_pipeline = False
        report = CiStabilizationService().stabilization_report()
        assert report["verdict"] == VERDICT_NOT_READY
        assert report["pipeline_ready"] is False
    finally:
        settings.ci_cd_require_green_pipeline = prev


def test_verdict_ready_when_no_blocking():
    service = CiStabilizationService()
    report = service.stabilization_report()
    if not report["blocking_issues"]:
        assert report["verdict"] == VERDICT_READY


def test_render_markdown_sections():
    md = CiStabilizationService().render_markdown()
    assert "# CI/CD Stabilization" in md
    assert "## Workflows" in md
    assert "## Testes flaky rastreados" in md


def test_live_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/ci-stabilization/live")
    assert r.status_code == 200
    assert "verdict" in r.json()


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/ci-stabilization/markdown")
    assert r.status_code == 200
    assert "# CI/CD Stabilization" in r.text


def test_validate_settings_rejects_disabled_gate_in_production():
    settings = get_settings()
    prev = settings.ci_cd_require_green_pipeline
    try:
        settings.ci_cd_require_green_pipeline = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("ci_cd_require_green_pipeline" in i for i in issues)
    finally:
        settings.ci_cd_require_green_pipeline = prev
