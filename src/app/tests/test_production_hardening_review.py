import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_production_hardening_blocks_default_jwt_without_exposing_secret():
    settings = get_settings()
    old = {
        "auth_required": settings.auth_required,
        "jwt_secret_key": settings.jwt_secret_key,
    }
    try:
        settings.auth_required = True
        settings.jwt_secret_key = "change-me-super-secret-local-key"
        with TestClient(app) as client:
            response = client.post("/api/v1/campaign-operator/production/hardening-review", json={})
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission_id"] == "production-hardening"
    assert data["status"] == "blocked"
    assert data["secrets_redacted"] is True
    blocked_names = {item["name"] for item in data["blocked_checks"]}
    assert "jwt_secret_rotated" in blocked_names
    assert "change-me-super-secret-local-key" not in json.dumps(data)


def test_production_hardening_can_be_ready_with_rotated_secret_and_limits():
    settings = get_settings()
    old = {
        "auth_required": settings.auth_required,
        "jwt_secret_key": settings.jwt_secret_key,
        "meta_operator_enabled": settings.meta_operator_enabled,
        "meta_require_manual_confirmation": settings.meta_require_manual_confirmation,
        "meta_production_daily_spend_limit_brl": settings.meta_production_daily_spend_limit_brl,
        "meta_created_resources_log": settings.meta_created_resources_log,
        "automation_level": settings.automation_level,
    }
    try:
        settings.auth_required = True
        settings.jwt_secret_key = "rotated-test-secret-value"
        settings.meta_operator_enabled = True
        settings.meta_require_manual_confirmation = True
        settings.meta_production_daily_spend_limit_brl = 50.0
        settings.meta_created_resources_log = "./logs/test_created_resources.jsonl"
        settings.automation_level = 1
        with TestClient(app) as client:
            response = client.post("/api/v1/campaign-operator/production/hardening-review", json={})
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] in {"ready", "ready_with_warnings"}
    assert data["blocked_checks"] == []
    assert data["published"] is False
    assert data["executed"] is False
    assert "rotated-test-secret-value" not in json.dumps(data)
