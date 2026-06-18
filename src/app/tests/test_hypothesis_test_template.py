from fastapi.testclient import TestClient

from app.core.hypothesis_test_template import hypothesis_test_01_template
from app.main import app


def test_hypothesis_test_01_template_is_safe_paused_lead_plan():
    plan = hypothesis_test_01_template({"product_name": "Produto Lead", "niche": "marketing"})

    assert plan["template_id"] == "TESTE_HIPOTESE_01"
    assert plan["will_execute_real_action"] is False
    assert plan["will_activate_spend"] is False
    assert plan["campaign"]["objective"] == "LEAD"
    assert plan["campaign"]["status"] == "PAUSED"
    assert plan["campaign"]["daily_budget_brl"] == 5
    assert "Lead" in plan["tracking"]["required_events"]
    assert plan["cut_metrics"]["minimum_ctr_percent"] == 1.5


def test_hypothesis_test_01_template_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/campaign-templates/hypothesis-test-01", json={"product_name": "Produto Lead"})

    assert response.status_code == 200
    data = response.json()
    assert data["campaign"]["status"] == "PAUSED"
    assert data["brain_brian_review"]["learning_recorded"] is True
