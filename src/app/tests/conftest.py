import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def disable_auth_for_legacy_smoke_tests():
    settings = get_settings()
    previous = settings.auth_required
    settings.auth_required = False
    try:
        yield
    finally:
        settings.auth_required = previous
