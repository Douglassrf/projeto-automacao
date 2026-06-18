from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.observability import audit_event, health_dashboard, observability_health


def test_observability_health_reports_trace_and_audit_support():
    health = observability_health()

    assert health["enabled"] is True
    assert health["correlation_id_supported"] is True
    assert health["execution_id_supported"] is True
    assert health["mission_id_supported"] is True
    assert Path(health["log_file"]).name == "observability_events.log"
    assert Path(health["audit_file"]).name == "audit_events.log"


def test_observability_middleware_returns_trace_headers():
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={
                "x-correlation-id": "corr-test",
                "x-execution-id": "exec-test",
                "x-mission-id": "27",
            },
        )

    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "corr-test"
    assert response.headers["x-execution-id"] == "exec-test"
    assert response.headers["x-mission-id"] == "27"


def test_audit_event_persists_structured_trace():
    record = audit_event(
        actor="Mission27Test",
        action="record",
        resource_type="observability",
        resource_id="memory-guard",
        mission_id="27",
        correlation_id="corr-audit-test",
        execution_id="exec-audit-test",
        details={"purpose": "prevent_forgetting"},
    )

    assert record["actor"] == "Mission27Test"
    assert record["action"] == "record"
    assert record["resource_type"] == "observability"
    assert record["mission_id"] == "27"
    assert record["correlation_id"] == "corr-audit-test"
    assert record["execution_id"] == "exec-audit-test"


def test_observability_dashboard_summarizes_routes_and_memory_guard():
    dashboard = health_dashboard(limit=5)

    assert dashboard["agent"] == "ObservabilityAgent"
    assert dashboard["audit_agent"] == "AuditLoggerAgent"
    assert dashboard["memory_guard"]["writes_project_logs"] is True
    assert dashboard["memory_guard"]["uses_correlation_id"] is True
    assert dashboard["loaded_routes"] >= 1
