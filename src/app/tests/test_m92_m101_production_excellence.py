from fastapi.testclient import TestClient

from app.main import app
from app.services.production_excellence_service import ProductionExcellenceService


def test_monitoring_center_has_operational_visibility():
    report = ProductionExcellenceService().monitoring_center()

    assert report["dashboard_status"] == "operational"
    assert report["services"]
    assert report["resource_consumption"]["cpu_avg_pct"] > 0
    assert report["latency"]["p95_ms"] <= report["latency"]["target_ms"]
    assert report["availability"]["current_pct"] >= report["availability"]["target_pct"]
    assert report["incident_history"][0]["timeline"]


def test_incident_manager_classifies_and_preserves_auditability():
    service = ProductionExcellenceService()
    classification = service.classify_incident({"availability_pct": 98.5, "latency_p95_ms": 1600, "error_rate_pct": 1.5})

    assert classification["severity"] == "sev2"
    assert classification["requires_war_room"] is True
    assert service.incident_history()[0]["audit_trail"].startswith("knowledge://incidents/")


def test_full_center_approves_production_excellence_certification():
    center = ProductionExcellenceService().full_center()

    assert center["service_levels"]["continuous_calculation"] is True
    assert center["capacity_planning"]["forecasts"]
    assert center["operational_analytics"]["automated_reports"] is True
    assert center["continuous_compliance"]["non_conformities"] == []
    assert center["knowledge_center"]["last_review_status"] == "updated"
    assert center["maintenance_planner"]["preventive_plan_active"] is True
    assert center["executive_governance"]["pending"] == []
    assert center["production_certification"]["approved"] is True


def test_production_excellence_routes_are_available():
    with TestClient(app) as client:
        response = client.get("/api/v1/production-excellence/full-center")

    assert response.status_code == 200
    payload = response.json()
    assert payload["monitoring_center"]["dashboard_status"] == "operational"
    assert payload["production_certification"]["technical_board_approval"] == "approved"
