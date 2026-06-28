"""Missao 85."""
from fastapi.testclient import TestClient

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.release_candidate_service import ReleaseCandidateService

def test_report_shape():
    report = ReleaseCandidateService().rc1_report()
    assert report["mission_number"] == 85
    assert "verdict" in report


def test_config_version():
    assert CONFIG_SCHEMA_VERSION == "3.4.0"


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/release-candidate/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/release-candidate/markdown")
    assert r.status_code == 200
