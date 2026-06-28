"""Missão 81 — Integração Controlada (capstone)."""

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.services.integration_control_service import get_integration_control_service


def test_merge_health_report_reports_m81_metadata():
    report = get_integration_control_service().merge_health_report()
    assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (4, 0, 0)
    assert report["loaded_routes"] > 0
    assert report["mission_60_status"] == "not_ready"
    assert "missao-60" in report["mission_60_note"]


def test_merge_health_report_fail_closed_on_route_failures():
    report = get_integration_control_service().merge_health_report()
    if not report["failed_routes"]:
        assert report["verdict"] == "ready"
    else:
        assert report["verdict"] == "not_ready"
