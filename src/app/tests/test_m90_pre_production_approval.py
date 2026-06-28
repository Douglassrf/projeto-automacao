"""Missao 90."""
from fastapi.testclient import TestClient

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.pre_production_approval_service import PreProductionApprovalService

def test_report_shape():
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        report = PreProductionApprovalService(db).approval_report()
        assert report["mission_number"] == 90
        assert "verdict" in report
    finally:
        db.close()


def test_config_version():
    assert CONFIG_SCHEMA_VERSION == "3.9.0"


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/pre-production-approval/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/pre-production-approval/markdown")
    assert r.status_code == 200
