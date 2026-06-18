from fastapi.testclient import TestClient

from app.core.sandbox_readiness import sandbox_readiness_report
from app.main import app


def test_sandbox_readiness_reports_ready_for_sandbox_but_not_production():
    report = sandbox_readiness_report({"target": "meta"})

    assert report["status"] == "ready_for_sandbox_review"
    assert report["sandbox_ready"] is True
    assert report["production_ready"] is False
    assert "requires_separate_sandbox_or_test_account" in report["production_blockers"]
    assert "validar conta sandbox/test_account separada" in report["required_next_steps"]


def test_sandbox_readiness_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/security/sandbox-readiness", json={"target": "meta"})

    assert response.status_code == 200
    assert response.json()["sandbox_ready"] is True
