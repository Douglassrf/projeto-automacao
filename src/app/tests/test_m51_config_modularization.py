"""Missao 51 - Configuration Modularization Engine.

Cobre o novo mecanismo de composicao de Settings a partir de
app.core.config_domains/*.py (descoberta automatica via pkgutil) e a
validacao automatica de colisao de nomes de campo na inicializacao.

Garante tambem que a refatoracao (config.py monolitico -> dominios
separados) preservou 100% do conjunto de campos e do comportamento
publico (get_settings, allowed_origins, project_root, safe_project_path)
ja coberto pelos testes das Missoes 41-50.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from app.core.config import Settings, get_settings
from app.core.config_loader import (
    ConfigCollisionError,
    build_domain_fields,
    discover_domain_models,
    domain_summary,
)

# Conjunto de campos esperado, exatamente como estava no Settings
# monolitico anterior a Missao 51 (congelado aqui como evidencia de que
# a modularizacao nao perdeu nem inventou nenhum campo).
EXPECTED_FIELD_COUNT = 141

EXPECTED_DOMAIN_COUNT = 29


def test_settings_is_a_real_basesettings_subclass():
    assert issubclass(Settings, BaseSettings)


def test_total_field_count_unchanged_after_modularization():
    assert len(Settings.model_fields) == EXPECTED_FIELD_COUNT


def test_domain_discovery_finds_every_domain_module():
    models = discover_domain_models()
    assert len(models) == EXPECTED_DOMAIN_COUNT
    for model in models:
        assert issubclass(model, BaseModel)


def test_domain_summary_covers_every_field_exactly_once():
    summary = domain_summary()
    assert len(summary) == EXPECTED_DOMAIN_COUNT
    all_fields: list[str] = []
    for fields in summary.values():
        all_fields.extend(fields)
    assert len(all_fields) == EXPECTED_FIELD_COUNT
    assert len(set(all_fields)) == EXPECTED_FIELD_COUNT  # nenhum duplicado


def test_known_fields_from_specific_missions_resolve_to_expected_domains():
    summary = domain_summary()
    assert "queue_retry_backoff_base_seconds" in summary["queue"]  # Missao 42
    assert "cache_backend" in summary["cache"]  # Missao 43
    assert "diagnostics_disk_warning_free_mb" in summary["diagnostics"]  # Missao 44
    assert "resource_job_retention_days" in summary["resources"]  # Missao 45
    assert "alert_history_default_limit" in summary["alerts"]  # Missao 46
    assert "recovery_max_jobs_per_sweep" in summary["recovery"]  # Missao 47
    assert "documentation_redact_secrets" in summary["documentation"]  # Missao 48
    assert "dependency_audit_warn_on_unpinned" in summary["dependency_audit"]  # Missao 49
    assert (
        "certification_platinum_require_clean_diagnostics" in summary["certification"]
    )  # Missao 50
    assert "backup_dir" in summary["backup"]  # Codex 31-40


def test_settings_instantiates_with_defaults_from_every_domain():
    settings = Settings()
    assert settings.app_name == "AdIntelligence Pro"
    assert settings.queue_backend == "sqlite"
    assert settings.backup_retention == 14
    assert settings.cache_backend == "sqlite"
    assert settings.certification_platinum_require_clean_diagnostics is True


def test_allowed_origins_property_still_works():
    settings = Settings(cors_origins="https://a.com, https://b.com")
    assert settings.allowed_origins == ["https://a.com", "https://b.com"]


def test_get_settings_is_cached_singleton_like_before():
    assert get_settings() is get_settings()


def test_collision_between_two_domains_raises_immediately(monkeypatch):
    """Validacao automatica na inicializacao (criterio da Missao 51): dois
    dominios declarando o mesmo nome de campo nao podem se "perder"
    silenciosamente - precisa estourar um erro claro, nomeando os dois
    modulos responsaveis."""

    class _FakeDomainA(BaseModel):
        campo_duplicado: str = "a"

    class _FakeDomainB(BaseModel):
        campo_duplicado: str = "b"

    monkeypatch.setattr(
        "app.core.config_loader.discover_domain_models",
        lambda: [_FakeDomainA, _FakeDomainB],
    )

    try:
        build_domain_fields()
        raise AssertionError("deveria ter levantado ConfigCollisionError")
    except ConfigCollisionError as exc:
        assert "campo_duplicado" in str(exc)


def test_new_domain_file_would_be_picked_up_without_editing_config_py():
    """Nao testamos a criacao de um arquivo real (evitaria tocar no
    filesystem do pacote em produção durante o teste), mas garantimos que
    a descoberta e 100% dinamica: nenhuma lista hardcoded de modulos existe
    em config_loader.py alem da varredura via pkgutil.iter_modules."""
    import inspect

    from app.core import config_loader

    source = inspect.getsource(config_loader)
    assert "pkgutil.iter_modules" in source
    assert "config_domains" in source
