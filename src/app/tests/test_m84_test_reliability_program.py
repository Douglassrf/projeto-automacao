"""Missao 84."""
from fastapi.testclient import TestClient

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.test_reliability_service import TestReliabilityService

def test_report_shape():
    report = TestReliabilityService().reliability_report()
    assert report["mission_number"] == 84
    assert "verdict" in report


def test_config_version():
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (3, 3, 0)


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/test-reliability/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/test-reliability/markdown")
    assert r.status_code == 200
