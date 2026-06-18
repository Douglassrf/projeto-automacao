from fastapi.testclient import TestClient

from app.core.security_status import security_hardening_status
from app.main import app


def test_security_hardening_status_reports_active_controls():
    status = security_hardening_status()

    assert status["status"] == "active_safe_mode"
    assert status["controls"]["rbac"] is True
    assert status["controls"]["api_gateway_guard"] is True
    assert status["controls"]["route_security_guard"] is True
    assert "MetaCampaignOperator" in status["service_accounts"]
    assert "meta_api" in status["rate_limit_rules"]


def test_security_status_endpoint_exposes_safe_policy():
    with TestClient(app) as client:
        response = client.get("/api/v1/security/status")

    assert response.status_code == 200
    data = response.json()
    assert data["real_execution_policy"]["default_to_dry_run"] is True
    assert "paid_ai_requires_manual_approval" in data["real_execution_policy"]
