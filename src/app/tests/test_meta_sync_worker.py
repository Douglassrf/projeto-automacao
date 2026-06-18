from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings


def auth_headers(client: TestClient) -> dict[str, str]:
    settings = get_settings()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": settings.default_admin_email, "password": settings.default_admin_password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_sync_meta_campaigns_dry_run_upserts_state_and_metrics():
    with TestClient(app) as client:
        headers = auth_headers(client)
        response = client.post(
            "/api/v1/campaign-intelligence/campaigns/sync-meta",
            json={"limit": 10, "dry_run": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["processed"] >= 1
        assert data["dry_run"] is True
        assert data["items"]
        first = data["items"][0]
        assert first["meta_campaign_id"]
        assert "spend_today" in first
        assert "daily_budget" in first
