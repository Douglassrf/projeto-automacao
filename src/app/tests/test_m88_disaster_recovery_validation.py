"""Missao 88."""
from fastapi.testclient import TestClient

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.disaster_recovery_validation_service import DisasterRecoveryValidationService

def test_report_shape():
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        report = DisasterRecoveryValidationService(db).validation_report()
        assert report["mission_number"] == 88
        assert "verdict" in report
    finally:
        db.close()


def test_config_version():
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (3, 7, 0)


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/disaster-recovery/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/disaster-recovery/markdown")
    assert r.status_code == 200
