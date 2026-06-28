"""Missão 52 — Dependency Injection Framework.

Cobre: a fabrica genérica `provide()` (gera um provider funcional para
qualquer service com `__init__(self, db: Session)`), o registro central de
providers (`registered_providers()`), `settings_dependency()` como wrapper
substituível de `get_settings()`, e a adoção real do container pelas rotas
de fila e cache (Missões 42/43) — provando, via `app.dependency_overrides`,
que a troca de implementação em teste funciona sem precisar mockar módulos.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.container import (
    get_alert_service,
    get_cache_service,
    get_certification_service,
    get_diagnostics_service,
    get_queue_service,
    get_recovery_service,
    get_resource_manager_service,
    provide,
    registered_providers,
    settings_dependency,
)
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.cache_service import CacheService
from app.services.queue_service import QueueService


def test_provide_returns_callable_dependency_factory():
    provider = provide(QueueService, name="QueueServiceTest")
    assert callable(provider)
    assert provider.__name__ == "provide_QueueServiceTest"


def test_provide_constructs_real_service_with_injected_db_session():
    provider = provide(CacheService, name="CacheServiceUnitTest")
    db = SessionLocal()
    try:
        service = provider(db=db)
        assert isinstance(service, CacheService)
        assert service.db is db
    finally:
        db.close()


def test_registered_providers_includes_all_seven_core_services():
    names = registered_providers()
    for expected in (
        "QueueService",
        "CacheService",
        "DiagnosticsService",
        "AlertService",
        "RecoveryService",
        "ResourceManagerService",
        "CertificationService",
    ):
        assert expected in names


def test_registered_providers_is_sorted_and_deduplicated():
    names = registered_providers()
    assert names == sorted(set(names))


def test_settings_dependency_returns_real_settings_instance():
    result = settings_dependency()
    assert isinstance(result, Settings)
    assert result is get_settings()


def test_settings_dependency_is_overridable_in_a_fastapi_app():
    app = FastAPI()

    @app.get("/whoami")
    def whoami(settings: Settings = Depends(settings_dependency)):
        return {"app_name": settings.app_name}

    fake_settings = Settings(app_name="settings-foi-trocada")
    app.dependency_overrides[settings_dependency] = lambda: fake_settings

    with TestClient(app) as client:
        response = client.get("/whoami")
        assert response.status_code == 200
        assert response.json()["app_name"] == "settings-foi-trocada"


def test_queue_and_cache_providers_are_overridable_without_touching_modules():
    """Prova de adesão real: as rotas /queue e /cache (Missões 42/43) usam
    get_queue_service/get_cache_service do container. Aqui substituímos a
    dependência por um fake simples, sem monkeypatch em nenhum módulo - se
    as rotas ainda chamassem `QueueService(db)` direto, esta troca não
    teria efeito nenhum na resposta."""

    class _FakeQueueService:
        def stats(self):
            return {
                "backend": "fake-em-teste",
                "queued": 0,
                "running": 0,
                "done": 0,
                "failed": 0,
                "dead": 0,
                "total": -1,
                "recommendation": "ok",
                "healthy": True,
                "warnings": [],
            }

    class _FakeCacheService:
        def stats(self, namespace=None):
            return {
                "backend": "fake-em-teste",
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "evictions": 0,
                "expired_purged": 0,
                "hit_rate": 0.0,
                "size": -1,
                "live_size": -1,
                "per_namespace": {},
            }

    real_app.dependency_overrides[get_queue_service] = lambda: _FakeQueueService()
    real_app.dependency_overrides[get_cache_service] = lambda: _FakeCacheService()
    try:
        with TestClient(real_app) as client:
            queue_response = client.get("/api/v1/queue/stats")
            cache_response = client.get("/api/v1/cache/stats")
    finally:
        real_app.dependency_overrides.pop(get_queue_service, None)
        real_app.dependency_overrides.pop(get_cache_service, None)

    assert queue_response.status_code == 200
    assert queue_response.json()["total"] == -1
    assert cache_response.status_code == 200
    assert cache_response.json()["size"] == -1


def test_all_seven_core_providers_are_distinct_callables():
    providers = [
        get_queue_service,
        get_cache_service,
        get_diagnostics_service,
        get_alert_service,
        get_recovery_service,
        get_resource_manager_service,
        get_certification_service,
    ]
    assert len(providers) == len(set(providers))
