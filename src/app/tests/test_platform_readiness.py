from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_self_diagnostic_returns_health_score_and_required_checks():
    response = client.get("/api/v1/platform-readiness/self-diagnostic")
    assert response.status_code == 200
    data = response.json()
    assert data["mission"] == "S01"
    assert 0 <= data["health_score"] <= 100
    assert {item["component"] for item in data["checks"]} >= {"database", "uploads", "memory", "dashboard", "notifications", "meta", "tiktok"}


def test_decision_assistant_is_read_only():
    response = client.get("/api/v1/platform-readiness/decision-assistant")
    assert response.status_code == 200
    data = response.json()
    assert data["mission"] == "S08"
    assert data["will_execute_real_action"] is False
    assert {"o_que_fazer", "qual_prioridade", "qual_risco"} <= set(data["answers"])


def test_final_flight_keeps_v11_scope_and_reports():
    response = client.get("/api/v1/platform-readiness/final-flight")
    assert response.status_code == 200
    data = response.json()
    assert data["phase"] == "X"
    assert data["v11_only"] is True
    assert data["no_new_business_features"] is True
    assert "AUTOMACAO_V11_FINAL_HOMOLOGATION.md" in data["required_reports"]
