from functools import lru_cache
from pathlib import Path

from pydantic import create_model
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config_loader import build_domain_fields
from app.core.config_profiles import (
    CONFIG_SCHEMA_VERSION,  # noqa: F401  (re-exportado por compatibilidade)
    detect_environment,
    env_file_candidates,
    validate_or_raise,
)

# Missao 51 - Configuration Modularization Engine.
#
# Settings deixou de declarar campos diretamente. Cada campo vive em um
# arquivo de dominio dedicado em app/core/config_domains/ (backup, cache,
# filas, seguranca, alertas, etc.) e e agregado automaticamente aqui via
# build_domain_fields() (descoberta por pkgutil, sem registro manual).
#
# Critério de sucesso: uma nova funcionalidade que precise de configuração
# NUNCA mais edita este arquivo - ela cria um novo módulo em
# config_domains/ com sua própria classe BaseModel e o campo passa a
# existir em Settings na próxima inicialização, automaticamente.
# M81: dominios 71-80 adicionados em config_domains/ (nao aqui).
_GeneratedSettings = create_model(
    "_GeneratedSettings",
    __base__=BaseSettings,
    **build_domain_fields(),
)


class Settings(_GeneratedSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Carrega Settings com perfil de ambiente (Missao 41).

    Compatibilidade garantida: se a variavel de ambiente APP_ENV nao estiver
    definida (caso de toda instalacao existente hoje), o perfil resolvido e
    "development" e os unicos arquivos candidatos sao (".env.development",
    ".env") - como ".env.development" tipicamente nao existe, o
    pydantic-settings o ignora silenciosamente e o comportamento final e
    identico ao de antes (carregar so ".env"). Variaveis de ambiente reais
    do processo continuam tendo precedencia sobre qualquer arquivo .env*.
    """
    environment = detect_environment()
    settings = Settings(_env_file=env_file_candidates(environment))
    validate_or_raise(settings, environment)
    return settings


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def safe_project_path(configured_dir: str, fallback_relative: str) -> Path:
    configured = Path(configured_dir).resolve()
    try:
        configured.mkdir(parents=True, exist_ok=True)
        probe = configured / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return configured
    except OSError:
        return ensure_writable_dir(project_root() / fallback_relative)
        
def ensure_writable_dir(path: str | Path) -> Path:
    target = Path(path)
    try: target.mkdir(parents=True, exist_ok=True); probe = target / ".write_probe"; probe.write_text("ok", encoding="utf-8"); probe.unlink(missing_ok=True); return target
    except OSError:
        import tempfile
        try: relative = target.resolve().relative_to(project_root())
        except ValueError: relative = Path(target.name)
        fallback = Path(tempfile.gettempdir()) / "projeto_automacao_runtime" / relative; fallback.mkdir(parents=True, exist_ok=True); return fallback
