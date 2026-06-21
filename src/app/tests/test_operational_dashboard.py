from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.operational_dashboard import operational_dashboard_snapshot
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.domain.models import User
from app.main import app


def _auth_headers() -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "dashboard-test@example.com").first()
        if user is not None and user.id == 1:
            db.delete(user)
            db.commit()
            user = None
        if user is None:
            user = User(
                id=999999,
                name="Dashboard Test",
                email="dashboard-test@example.com",
                access_level="DEV",
                hashed_password=hash_password("dashboard-test-password"),
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token(str(user.id), extra={"email": user.email})
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


def test_operational_dashboard_snapshot_is_read_only_unified_view():
    db = SessionLocal()
    try:
        snapshot = operational_dashboard_snapshot(db)
    finally:
        db.close()

    assert snapshot["mode"]["read_only_dashboard"] is True
    assert "security" in snapshot
    assert "queues" in snapshot
    assert "audit" in snapshot
    assert "connectors" in snapshot
    assert "campaigns" in snapshot
    assert "alerts" in snapshot
    assert "tasks" in snapshot
    assert snapshot["connectors"]["network_access_used"] is False
    assert snapshot["connectors"]["credentials_loaded"] is False


def test_operational_dashboard_requires_auth_when_auth_required_true():
    settings = get_settings()
    previous = settings.auth_required
    settings.auth_required = True
    try:
        with TestClient(app) as client:
            unauthenticated = client.get("/api/v1/dashboard/operational")
            assert unauthenticated.status_code == 401

            authenticated = client.get("/api/v1/dashboard/operational", headers=_auth_headers())
            assert authenticated.status_code == 200, authenticated.text
            data = authenticated.json()
            assert data["mode"]["auth_required"] is True
            assert data["mode"]["read_only_dashboard"] is True
            assert data["tasks"]["pending_meta_actions"] >= 0
    finally:
        settings.auth_required = previous


def test_operational_dashboard_ui_matches_dark_reference_sections_and_auth():
    settings = get_settings()
    previous = settings.auth_required
    settings.auth_required = True
    try:
        with TestClient(app) as client:
            unauthenticated = client.get("/api/v1/dashboard/operational/ui")
            assert unauthenticated.status_code == 401

            response = client.get("/api/v1/dashboard/operational/ui", headers=_auth_headers())
            assert response.status_code == 200, response.text
            html = response.text
            assert "AUTOMAÇÃO" in html
            assert "v1.0" in html
            assert "Olá," in html
            assert 'O que vamos <span class="gradient-word">criar</span> hoje?' in html
            assert "Ações rápidas" in html
            assert "Como funciona?" in html
            assert "Atividades recentes" in html
            assert "Automações ativas" in html
            assert "Saúde do sistema" in html
            assert "Visão geral" in html
            assert "Ferramentas rápidas" in html
            assert "CRIAR" in html
            assert "GERENCIAR" in html
            assert "INTELIGÊNCIA" in html
            assert "CONFIGURAÇÕES" in html
            assert "DOUGLAS PRIME" in html
            assert "Sistema " in html
            assert "grid-template-columns: 282px minmax(0, 1fr) 390px" in html
            assert "linear-gradient" in html
            assert "Criar Campanha" in html
            assert "Gerar Criativos" in html
            assert "Publicamos e monitoramos" in html
    finally:
        settings.auth_required = previous
