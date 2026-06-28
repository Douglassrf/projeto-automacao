"""Missao 89."""
from fastapi.testclient import TestClient

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.documentation_review_service import DocumentationReviewService

def test_report_shape():
    report = DocumentationReviewService().review_report()
    assert report["mission_number"] == 89
    assert "verdict" in report


def test_config_version():
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (3, 8, 0)


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/documentation-review/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/documentation-review/markdown")
    assert r.status_code == 200
