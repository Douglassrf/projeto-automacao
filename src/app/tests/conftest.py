import pytest

from app.core.config import get_settings
from app.db.session import Base, engine


@pytest.fixture(scope="session", autouse=True)
def ensure_database_schema():
    settings = get_settings()
    if settings.default_admin_password is None:
        settings.default_admin_password = "test-admin-password"
    # Garante que as tabelas existam antes de qualquer teste, independente da
    # ordem de coleta. Sem isso, testes que nao chamam init_db() explicitamente
    # (como test_auth.py) dependiam implicitamente de um banco real ja existente
    # com as tabelas criadas, falhando com "no such table" em um banco novo/vazio.
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def disable_auth_for_legacy_smoke_tests():
    settings = get_settings()
    previous = settings.auth_required
    settings.auth_required = False
    try:
        yield
    finally:
        settings.auth_required = previous
