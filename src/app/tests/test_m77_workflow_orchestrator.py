"""Missao 77 - Workflow Orchestrator."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.workflow_orchestrator_service import WorkflowOrchestratorService


def test_orchestration_report_shape():
    db = SessionLocal()
    try:
        report = WorkflowOrchestratorService(db).orchestration_report()
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert "workflow_steps" in report
        assert "queue_health" in report
    finally:
        db.close()


def test_progress_tracking_when_enabled():
    db = SessionLocal()
    try:
        report = WorkflowOrchestratorService(db).orchestration_report()
        assert "progress_pct" in report["progress"]
    finally:
        db.close()


def test_progress_empty_when_disabled():
    db = SessionLocal()
    settings = get_settings()
    prev = settings.workflow_orchestrator_track_progress
    try:
        settings.workflow_orchestrator_track_progress = False
        report = WorkflowOrchestratorService(db).orchestration_report()
        assert report["progress"] == {}
    finally:
        settings.workflow_orchestrator_track_progress = prev
        db.close()


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/workflow-orchestrator/status/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    assert "# Workflow Orchestrator" in client.get("/api/v1/workflow-orchestrator/status/markdown").text


def test_config_2_6_0():
    assert tuple(int(x) for x in CONFIG_SCHEMA_VERSION.split(".")) >= (2, 6, 0)


def test_validate_settings_rejects_disabled_progress_in_production():
    settings = get_settings()
    prev = settings.workflow_orchestrator_track_progress
    try:
        settings.workflow_orchestrator_track_progress = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("workflow_orchestrator_track_progress" in i for i in issues)
    finally:
        settings.workflow_orchestrator_track_progress = prev
