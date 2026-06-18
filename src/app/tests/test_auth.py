from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.init_db import init_db
from app.main import app


def test_personal_login_and_me():
    settings = get_settings()
    previous = settings.auth_required
    settings.auth_required = True
    try:
        init_db()
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": settings.default_admin_email, "password": settings.default_admin_password},
            )
            assert login.status_code == 200
            token = login.json()["access_token"]
            me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status_code == 200
            assert me.json()["email"] == settings.default_admin_email
    finally:
        settings.auth_required = previous
