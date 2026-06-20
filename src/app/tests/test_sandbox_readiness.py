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


def test_sandbox_readiness_blocks_when_security_controls_are_empty(monkeypatch):
    def fake_security_status():
        return {
            "status": "active_safe_mode",
            "controls": {},
        }

    def fake_gate(_payload):
        return {"status": "blocked", "blocked_reasons": ["human_approval_required"]}

    def fake_brain(_payload):
        return {"brain_review": {"decision": "NAO", "next_action": "fix_security_controls"}}

    monkeypatch.setattr("app.core.sandbox_readiness.security_hardening_status", fake_security_status)
    monkeypatch.setattr("app.core.sandbox_readiness.real_mode_readiness_gate", fake_gate)
    monkeypatch.setattr("app.core.sandbox_readiness.security_brain_review", fake_brain)

    report = sandbox_readiness_report({"target": "meta"})

    assert report["status"] == "blocked"
    assert report["sandbox_ready"] is False
    assert report["security_controls_active"] is False


def test_sandbox_readiness_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/security/sandbox-readiness", json={"target": "meta"})

    assert response.status_code == 200
    assert response.json()["sandbox_ready"] is True
