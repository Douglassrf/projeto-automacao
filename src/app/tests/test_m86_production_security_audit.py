"""Missao 86."""
from fastapi.testclient import TestClient

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.production_security_audit_service import ProductionSecurityAuditService

def test_report_shape():
    report = ProductionSecurityAuditService().audit_report()
    assert report["mission_number"] == 86
    assert "verdict" in report


def test_config_version():
    assert CONFIG_SCHEMA_VERSION == "3.5.0"


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/production-security-audit/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/production-security-audit/markdown")
    assert r.status_code == 200
