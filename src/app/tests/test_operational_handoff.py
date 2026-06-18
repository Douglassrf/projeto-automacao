from fastapi.testclient import TestClient

from app.core.operational_handoff import operational_handoff_checklist
from app.main import app


def test_operational_handoff_checklist_keeps_safe_boundaries():
    checklist = operational_handoff_checklist()

    assert checklist["status"] == "ready_for_safe_handoff"
    assert checklist["security_controls_active"] is True
    assert checklist["tests_expected"] == "172 passed"
    assert "/api/v1/campaign-templates/hypothesis-test-01" in checklist["safe_endpoints"]
    assert "qualquer gasto real" in checklist["blocked_until_user_approval"]


def test_operational_handoff_endpoint_is_available():
    with TestClient(app) as client:
        response = client.get("/api/v1/security/operational-handoff")

    assert response.status_code == 200
    data = response.json()
    assert data["sandbox_summary"]["production_ready"] is False
    assert "cmd /c VERIFICAR_PACOTE_FINAL.bat" in data["validation_commands"]
