"""Missão 81 — Integração Controlada (capstone)."""

from app.services.integration_control_service import integration_status


def test_integration_status_reports_m81_metadata():
    status = integration_status()
    assert status["mission"] == 81
    assert status["config_schema_version"] == "3.0.0"
    assert status["routes"]["loaded_count"] > 0
    assert status["m60"]["status"] == "not_ready"


def test_integration_status_fail_closed_on_route_failures():
    status = integration_status()
    if status["routes"]["failed_count"] == 0:
        assert status["verdict"] == "ready"
    else:
        assert status["verdict"] == "not_ready"
