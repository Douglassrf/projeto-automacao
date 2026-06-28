"""Domínio: identidade e ambiente base da aplicação (Missão 41)."""

from pydantic import BaseModel, Field

from app.core.config_profiles import CONFIG_SCHEMA_VERSION


class CoreConfig(BaseModel):
    # Missao 41 - Configuracao Centralizada: versao do esquema de config,
    # nao da aplicacao. Ver CONFIG_CHANGELOG.md.
    config_schema_version: str = CONFIG_SCHEMA_VERSION
    # Migrado de um os.getenv("APP_LOG_LEVEL", ...) disperso em
    # app/services/observability.py. None = usa observability_log_level.
    app_log_level: str | None = Field(default=None, validation_alias="APP_LOG_LEVEL")
    app_name: str = "AdIntelligence Pro"
    app_env: str = "dev"
    database_url: str = "sqlite:///./adintelligence.db"
