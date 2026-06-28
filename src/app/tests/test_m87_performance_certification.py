"""Missao 87."""
from fastapi.testclient import TestClient

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.performance_certification_service import PerformanceCertificationService

def test_report_shape():
    report = PerformanceCertificationService().performance_report()
    assert report["mission_number"] == 87
    assert "verdict" in report


def test_config_version():
    assert CONFIG_SCHEMA_VERSION == "3.6.0"


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/performance-certification/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/performance-certification/markdown")
    assert r.status_code == 200
