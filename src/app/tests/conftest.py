import pytest

from app.core.config import get_settings
from app.db.init_db import _ensure_sqlite_columns
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
    # Missao 42: create_all() so cria tabelas que nao existem - nao adiciona
    # colunas novas (ex.: queue_jobs.next_attempt_at) a um banco local que ja
    # tinha a tabela de uma sessao de testes anterior. Sem isto, qualquer
    # desenvolvedor com um adintelligence.db pre-existente (mesmo sendo um
    # arquivo de uso local, fora do git) veria "no such column" em testes que
    # nao chamam init_db() diretamente. Mantem o mesmo helper de migracao leve
    # ja usado em produção (app/db/init_db.py), sem introduzir Alembic.
    _ensure_sqlite_columns()


@pytest.fixture(autouse=True)
def disable_auth_for_legacy_smoke_tests():
    settings = get_settings()
    previous = settings.auth_required
    settings.auth_required = False
    try:
        yield
    finally:
        settings.auth_required = previous
