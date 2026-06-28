"""Missao 41 - Configuracao Centralizada.

Cobre o novo modulo app.core.config_profiles: deteccao de perfil,
resolucao de arquivos .env por perfil, validacao de configuracao critica
e o novo campo de versionamento de esquema em Settings. Tambem garante
que a migracao de APP_LOG_LEVEL em observability.py nao regrediu o
comportamento dinamico ja coberto por test_m06a_observability.py.
"""

import os

import pytest

from app.core.config import Settings, get_settings
from app.core.config_profiles import (
    CONFIG_SCHEMA_VERSION,
    ConfigValidationError,
    Environment,
    config_fingerprint,
    detect_environment,
    env_file_candidates,
    validate_or_raise,
    validate_settings,
)


def test_config_schema_version_is_exposed_on_settings():
    settings = get_settings()
    assert settings.config_schema_version == CONFIG_SCHEMA_VERSION
    assert CONFIG_SCHEMA_VERSION.count(".") == 2  # semver simples X.Y.Z


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, Environment.DEVELOPMENT),
        ("", Environment.DEVELOPMENT),
        ("development", Environment.DEVELOPMENT),
        ("dev", Environment.DEVELOPMENT),
        ("desenvolvimento", Environment.DEVELOPMENT),
        ("testing", Environment.TESTING),
        ("test", Environment.TESTING),
        ("teste", Environment.TESTING),
        ("staging", Environment.STAGING),
        ("homologacao", Environment.STAGING),
        ("HOMOLOGAÇÃO", Environment.STAGING),
        ("production", Environment.PRODUCTION),
        ("PROD", Environment.PRODUCTION),
        ("producao", Environment.PRODUCTION),
        ("valor-desconhecido-xyz", Environment.DEVELOPMENT),  # fallback seguro
    ],
)
def test_detect_environment_aliases(raw, expected):
    assert detect_environment(raw) is expected


def test_detect_environment_reads_app_env_from_os_environ(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    assert detect_environment() is Environment.STAGING
    monkeypatch.delenv("APP_ENV", raising=False)
    assert detect_environment() is Environment.DEVELOPMENT


def test_env_file_candidates_order_and_shape():
    for env in Environment:
        candidates = env_file_candidates(env)
        assert candidates == (f".env.{env.value}", ".env")
        # ".env" sempre por ultimo: maior precedencia (pydantic-settings)
        assert candidates[-1] == ".env"


def test_validate_settings_flags_unsafe_production_defaults():
    settings = Settings(_env_file=())
    issues = validate_settings(settings, Environment.PRODUCTION)
    assert any("jwt_secret_key" in issue for issue in issues)
    assert any("default_admin_password" in issue for issue in issues)


def test_validate_settings_clean_for_development_with_same_defaults():
    settings = Settings(_env_file=())
    issues = validate_settings(settings, Environment.DEVELOPMENT)
    # Os mesmos defaults de dev nao violam nenhuma regra de development.
    assert issues == []


def test_validate_or_raise_raises_for_production_but_not_development():
    settings = Settings(_env_file=())
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_or_raise(settings, Environment.PRODUCTION)
    assert excinfo.value.environment is Environment.PRODUCTION
    assert len(excinfo.value.issues) >= 1
    # Nao deve levantar para development com a mesma configuracao.
    validate_or_raise(settings, Environment.DEVELOPMENT)


def test_validate_or_raise_blocks_meta_production_in_testing_profile():
    settings = Settings(_env_file=())
    settings.meta_env = "production"
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_or_raise(settings, Environment.TESTING)
    assert any("meta_env" in issue for issue in excinfo.value.issues)


def test_validate_settings_rejects_non_positive_upload_limit():
    settings = Settings(_env_file=())
    settings.upload_max_bytes = 0
    issues = validate_settings(settings, Environment.STAGING)
    assert any("upload_max_bytes" in issue for issue in issues)


def test_validate_settings_rejects_zero_queue_attempts():
    settings = Settings(_env_file=())
    settings.queue_default_max_attempts = 0
    issues = validate_settings(settings, Environment.DEVELOPMENT)
    assert any("queue_default_max_attempts" in issue for issue in issues)


def test_get_settings_does_not_raise_when_app_env_unset(monkeypatch):
    """Garantia central de compatibilidade: nenhuma instalacao existente
    define APP_ENV hoje, e nenhuma delas deve passar a falhar ao chamar
    get_settings() por causa da Missao 41."""
    monkeypatch.delenv("APP_ENV", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.config_schema_version == CONFIG_SCHEMA_VERSION
    finally:
        get_settings.cache_clear()
        # Restaura o invariante que o fixture de sessao
        # (tests/conftest.py::ensure_database_schema) estabeleceu uma unica
        # vez no inicio da suite: default_admin_password preenchido para
        # testes que fazem login. get_settings.cache_clear() destroi o
        # singleton que aquele fixture mutou, e o fixture nao roda de novo
        # (scope="session"), entao recriamos o mesmo invariante aqui para
        # nao quebrar qualquer teste que rode depois deste na mesma sessao.
        restored = get_settings()
        if restored.default_admin_password is None:
            restored.default_admin_password = "test-admin-password"


def test_get_settings_raises_for_production_with_unsafe_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigValidationError):
            get_settings()
    finally:
        monkeypatch.delenv("APP_ENV", raising=False)
        get_settings.cache_clear()
        # Restaura o invariante que o fixture de sessao
        # (tests/conftest.py::ensure_database_schema) estabeleceu uma unica
        # vez no inicio da suite: default_admin_password preenchido para
        # testes que fazem login. get_settings.cache_clear() destroi o
        # singleton que aquele fixture mutou, e o fixture nao roda de novo
        # (scope="session"), entao recriamos o mesmo invariante aqui para
        # nao quebrar qualquer teste que rode depois deste na mesma sessao.
        restored = get_settings()
        if restored.default_admin_password is None:
            restored.default_admin_password = "test-admin-password"


def test_get_settings_accepts_production_with_safe_overrides(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "SenhaForteDeProducao!2026")
    monkeypatch.setenv("META_ALLOW_PRODUCTION_REAL", "false")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.jwt_secret_key == "x" * 40
    finally:
        for key in ("JWT_SECRET_KEY", "DEFAULT_ADMIN_PASSWORD", "META_ALLOW_PRODUCTION_REAL"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("APP_ENV", raising=False)
        get_settings.cache_clear()
        # Restaura o invariante que o fixture de sessao
        # (tests/conftest.py::ensure_database_schema) estabeleceu uma unica
        # vez no inicio da suite: default_admin_password preenchido para
        # testes que fazem login. get_settings.cache_clear() destroi o
        # singleton que aquele fixture mutou, e o fixture nao roda de novo
        # (scope="session"), entao recriamos o mesmo invariante aqui para
        # nao quebrar qualquer teste que rode depois deste na mesma sessao.
        restored = get_settings()
        if restored.default_admin_password is None:
            restored.default_admin_password = "test-admin-password"


def test_config_fingerprint_never_exposes_secret_values():
    settings = get_settings()
    original_secret = settings.jwt_secret_key
    try:
        settings.jwt_secret_key = "valor-bem-secreto-que-nao-pode-aparecer"
        fp = config_fingerprint(settings)
        dump = repr(fp)
        assert "valor-bem-secreto-que-nao-pode-aparecer" not in dump
        assert "jwt_secret_key" in fp["redacted_fields"]
        assert fp["config_schema_version"] == CONFIG_SCHEMA_VERSION
    finally:
        # get_settings() e um singleton via lru_cache; mutar um atributo
        # sem restaurar contaminaria todos os testes que rodarem depois
        # deste na mesma sessao de pytest (foi exatamente isso que
        # aconteceu na primeira versao deste teste - ver M41 report).
        settings.jwt_secret_key = original_secret


def test_app_log_level_field_reads_validation_alias(monkeypatch):
    monkeypatch.setenv("APP_LOG_LEVEL", "WARNING")
    settings = Settings(_env_file=())
    assert settings.app_log_level == "WARNING"
    monkeypatch.delenv("APP_LOG_LEVEL", raising=False)


def test_app_log_level_defaults_to_none_when_unset(monkeypatch):
    monkeypatch.delenv("APP_LOG_LEVEL", raising=False)
    settings = Settings(_env_file=())
    assert settings.app_log_level is None
