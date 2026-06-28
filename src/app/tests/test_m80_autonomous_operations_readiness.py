"""Missao 80 - Autonomous Operations Readiness (CAPSTONE)."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.autonomous_operations_service import (
    DOMAINS,
    VERDICT_NOT_READY,
    VERDICT_READY,
    AutonomousOperationsService,
)


def test_readiness_report_shape():
    db = SessionLocal()
    try:
        report = AutonomousOperationsService(db).readiness_report()
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert "verdict" in report
        assert "blocking_issues" in report
        assert "evidence" in report
        assert "domain_status" in report
        assert len(report["domains_tracked"]) == len(DOMAINS)
    finally:
        db.close()


def test_ten_domains_tracked():
    assert len(DOMAINS) == 10


def test_verdict_not_ready_when_gate_disabled():
    db = SessionLocal()
    settings = get_settings()
    prev = settings.autonomous_ops_require_all_domains
    try:
        settings.autonomous_ops_require_all_domains = False
        report = AutonomousOperationsService(db).readiness_report()
        assert report["verdict"] == VERDICT_NOT_READY
        assert report["autonomous_operations_ready"] is False
    finally:
        settings.autonomous_ops_require_all_domains = prev
        db.close()


def test_blocking_issues_always_calculated():
    db = SessionLocal()
    try:
        report = AutonomousOperationsService(db).readiness_report()
        assert isinstance(report["blocking_issues"], list)
        assert report["blocking_issue_count"] == len(report["blocking_issues"])
    finally:
        db.close()


def test_evidence_contains_key_metrics():
    db = SessionLocal()
    try:
        report = AutonomousOperationsService(db).readiness_report()
        evidence = report["evidence"]
        assert "certification_platinum" in evidence
        assert "operational_status" in evidence
        assert "quality_gate_passed" in evidence
    finally:
        db.close()


def test_render_markdown_sections():
    db = SessionLocal()
    try:
        md = AutonomousOperationsService(db).render_markdown()
        assert "# Autonomous Operations Readiness" in md
        assert "## Blocking issues" in md
        assert "## Dominios" in md
        assert "## Evidencias" in md
    finally:
        db.close()


def test_live_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/autonomous-operations/readiness/live")
    assert r.status_code == 200
    assert "verdict" in r.json()


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/autonomous-operations/readiness/markdown")
    assert r.status_code == 200
    assert "# Autonomous Operations Readiness" in r.text


def test_config_3_0_0():
    assert tuple(int(x) for x in CONFIG_SCHEMA_VERSION.split(".")) >= (3, 0, 0)


def test_validate_settings_rejects_disabled_gate_in_production():
    settings = get_settings()
    prev = settings.autonomous_ops_require_all_domains
    try:
        settings.autonomous_ops_require_all_domains = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("autonomous_ops_require_all_domains" in i for i in issues)
    finally:
        settings.autonomous_ops_require_all_domains = prev


def test_verdict_ready_when_no_blocking_issues():
    db = SessionLocal()
    try:
        service = AutonomousOperationsService(db)
        verdict = service._verdict([], "healthy")
        assert verdict == VERDICT_READY
    finally:
        db.close()
