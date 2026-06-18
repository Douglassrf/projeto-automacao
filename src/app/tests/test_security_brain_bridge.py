from fastapi.testclient import TestClient

from app.core.security_brain_bridge import security_brain_review
from app.main import app


def test_security_brain_bridge_records_gate_learning():
    result = security_brain_review({"target": "meta"})

    assert result["agent"] == "SecurityBrainBridge"
    assert result["security_status"]["controls_active"] is True
    assert result["real_mode_gate"]["status"] == "blocked"
    assert "human_approval_required" in result["real_mode_gate"]["blocked_reasons"]
    assert result["brain_review"]["decision"] in {"SIM", "NÃƒO"}
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_security_brain_review_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/security/brain-review", json={"target": "meta"})

    assert response.status_code == 200
    data = response.json()
    assert data["agent"] == "SecurityBrainBridge"
    assert "real_mode_gate" in data
