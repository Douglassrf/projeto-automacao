"""Missao 91."""
from fastapi.testclient import TestClient

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.production_launch_authorization_service import ProductionLaunchAuthorizationService

def test_report_shape():
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        report = ProductionLaunchAuthorizationService(db).authorization_report()
        assert report["mission_number"] == 91
        assert "verdict" in report
    finally:
        db.close()


def test_config_version():
    assert CONFIG_SCHEMA_VERSION == "4.0.0"


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/production-launch/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/production-launch/markdown")
    assert r.status_code == 200
