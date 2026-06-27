"""Missão 41 — Configuração Centralizada.

Camada de perfis, validação e versionamento sobre o `Settings` já existente em
`app.core.config`. Não substitui o `Settings`: adiciona o que faltava
(perfis Dev/Test/Homologação/Produção, validação automática de combinações
perigosas e um número de versão para o esquema de configuração), mantendo
100% de compatibilidade com quem já chama `get_settings()` hoje.

Princípio de design: zero variável de ambiente nova é exigida para o
comportamento atual continuar idêntico. `APP_ENV` é opcional; se ausente,
o perfil é "development" e o carregamento de arquivo é exatamente o mesmo
de antes (`.env`). Variáveis de ambiente reais do processo sempre têm
precedência sobre qualquer arquivo `.env*` — isso é garantia do próprio
pydantic-settings e não foi alterado aqui.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # evita import circular em tempo de execução
    from app.core.config import Settings

# Versão do ESQUEMA de configuração (não é a versão do app). Sobe quando um
# campo crítico é adicionado/removido/muda de significado em `Settings`.
# Ver CONFIG_CHANGELOG.md na raiz do repositório para o histórico completo.
CONFIG_SCHEMA_VERSION = "1.7.0"

# Placeholder conhecido de jwt_secret_key (valor de desenvolvimento em
# app/core/config.py). Produção nunca pode rodar com este valor.
_DEFAULT_JWT_SECRET_PLACEHOLDER = "change-me-super-secret-local-key"

# Nome real da variável de ambiente. Mantido fora de Settings de propósito:
# o perfil precisa ser conhecido ANTES de instanciar Settings, para decidir
# quais arquivos .env carregar.
_APP_ENV_VAR = "APP_ENV"


class Environment(str, Enum):
    """Os quatro perfis exigidos pela Missão 41."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"  # homologação
    PRODUCTION = "production"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


# Aliases em português/variações comuns aceitas em APP_ENV, para não forçar
# todo mundo a escrever exatamente "staging" em inglês.
_ENV_ALIASES = {
    "dev": Environment.DEVELOPMENT,
    "development": Environment.DEVELOPMENT,
    "desenvolvimento": Environment.DEVELOPMENT,
    "test": Environment.TESTING,
    "testing": Environment.TESTING,
    "teste": Environment.TESTING,
    "homolog": Environment.STAGING,
    "homologacao": Environment.STAGING,
    "homologação": Environment.STAGING,
    "staging": Environment.STAGING,
    "stage": Environment.STAGING,
    "prod": Environment.PRODUCTION,
    "production": Environment.PRODUCTION,
    "producao": Environment.PRODUCTION,
    "produção": Environment.PRODUCTION,
}


class ConfigValidationError(ValueError):
    """Levantado quando uma combinação de configuração é inválida/perigosa
    demais para o perfil corrente. Contém TODOS os problemas encontrados,
    não só o primeiro — quem for corrigir o .env quer ver a lista completa
    de uma vez."""

    def __init__(self, environment: "Environment", issues: list[str]):
        self.environment = environment
        self.issues = issues
        message = (
            f"Configuração inválida para o perfil '{environment.value}' "
            f"({len(issues)} problema(s)):\n- " + "\n- ".join(issues)
        )
        super().__init__(message)


def detect_environment(raw: str | None = None) -> Environment:
    """Determina o perfil ativo a partir de APP_ENV (ou do valor passado
    explicitamente). Desconhecido ou ausente -> development, igual ao
    comportamento de hoje (sem APP_ENV definido em lugar nenhum do projeto)."""

    value = raw if raw is not None else os.environ.get(_APP_ENV_VAR)
    if not value:
        return Environment.DEVELOPMENT
    normalized = value.strip().lower()
    if normalized in _ENV_ALIASES:
        return _ENV_ALIASES[normalized]
    try:
        return Environment(normalized)
    except ValueError:
        # Valor desconhecido: cai para development em vez de quebrar o
        # processo só por causa de um typo em APP_ENV.
        return Environment.DEVELOPMENT


def env_file_candidates(environment: Environment) -> tuple[str, ...]:
    """Lista de arquivos .env a carregar, em ordem de precedência CRESCENTE
    (pydantic-settings: arquivos depois na lista sobrescrevem os de antes).

    `.env.<perfil>` carrega primeiro (defaults do perfil); `.env` carrega
    depois e pode sobrescrever localmente. Arquivos inexistentes são
    silenciosamente ignorados pelo pydantic-settings — por isso isto é
    seguro mesmo em ambientes que nunca criaram esses arquivos."""

    return (f".env.{environment.value}", ".env")


def validate_settings(settings: "Settings", environment: Environment) -> list[str]:
    """Retorna a lista de problemas encontrados (vazia = configuração ok).
    Não lança exceção — quem decide se isso é fatal é `validate_or_raise`
    ou o chamador."""

    issues: list[str] = []

    if environment is Environment.PRODUCTION:
        if not settings.auth_required:
            issues.append(
                "auth_required=False em produção: todas as rotas autenticadas ficariam abertas."
            )
        if settings.jwt_secret_key == _DEFAULT_JWT_SECRET_PLACEHOLDER:
            issues.append(
                "jwt_secret_key ainda é o valor padrão de desenvolvimento "
                f"('{_DEFAULT_JWT_SECRET_PLACEHOLDER}'); gere um segredo real antes de produção."
            )
        if len(settings.jwt_secret_key) < 32:
            issues.append(
                f"jwt_secret_key tem {len(settings.jwt_secret_key)} caracteres; "
                "recomendado >= 32 para HMAC-SHA256 (ver RFC 7518 3.2)."
            )
        if settings.meta_env == "production" and settings.meta_dry_run:
            # Isso não é incoerente por si só (dry_run é a rede de segurança),
            # mas avisa para não ser confundido com "já está publicando real".
            issues.append(
                "meta_env='production' com meta_dry_run=True: nenhuma chamada real "
                "será feita à Meta API neste perfil — confirme se é intencional."
            )
        if settings.meta_allow_production_real and not settings.meta_require_manual_confirmation:
            issues.append(
                "meta_allow_production_real=True com meta_require_manual_confirmation=False: "
                "publicação real na Meta sem confirmação manual obrigatória."
            )
        if settings.default_admin_password is None:
            issues.append(
                "default_admin_password não definido em produção "
                "(o admin default usaria senha ausente/fraca)."
            )
        if not settings.documentation_redact_secrets:
            # Missao 48 - Documentacao Viva: os endpoints /documentation/*
            # expoem o schema de Settings. Sem redacao, qualquer campo com
            # "secret"/"password"/"token"/"key" no nome devolveria o valor
            # real (ex.: jwt_secret_key, meta_access_token) em texto puro.
            issues.append(
                "documentation_redact_secrets=False em produção: os endpoints "
                "/documentation/* exporiam valores reais de campos de segredo."
            )

    if environment is Environment.TESTING:
        if settings.meta_env == "production":
            issues.append(
                "meta_env='production' no perfil de testes: testes não devem apontar para a Meta API real."
            )
        if settings.meta_allow_production_real:
            issues.append(
                "meta_allow_production_real=True no perfil de testes: risco de side-effect real durante CI."
            )

    if settings.upload_max_bytes <= 0:
        issues.append(f"upload_max_bytes={settings.upload_max_bytes}: precisa ser positivo.")

    if settings.queue_default_max_attempts < 1:
        issues.append(
            f"queue_default_max_attempts={settings.queue_default_max_attempts}: precisa ser >= 1."
        )

    # Missao 42 - Gerenciador Inteligente de Filas.
    if settings.queue_retry_backoff_base_seconds < 1:
        issues.append(
            f"queue_retry_backoff_base_seconds={settings.queue_retry_backoff_base_seconds}: precisa ser >= 1."
        )
    if settings.queue_retry_backoff_max_seconds < settings.queue_retry_backoff_base_seconds:
        issues.append(
            "queue_retry_backoff_max_seconds "
            f"({settings.queue_retry_backoff_max_seconds}) menor que queue_retry_backoff_base_seconds "
            f"({settings.queue_retry_backoff_base_seconds}): o backoff nunca cresceria."
        )
    if settings.queue_starvation_threshold_seconds < 1:
        issues.append(
            f"queue_starvation_threshold_seconds={settings.queue_starvation_threshold_seconds}: precisa ser >= 1."
        )
    if not (0.0 < settings.queue_failure_rate_threshold <= 1.0):
        issues.append(
            f"queue_failure_rate_threshold={settings.queue_failure_rate_threshold}: precisa estar entre 0 (exclusivo) e 1 (inclusivo)."
        )

    # Missao 43 - Cache Inteligente.
    if settings.cache_default_ttl_seconds < 1:
        issues.append(
            f"cache_default_ttl_seconds={settings.cache_default_ttl_seconds}: precisa ser >= 1."
        )
    if settings.cache_max_entries_per_namespace < 1:
        issues.append(
            f"cache_max_entries_per_namespace={settings.cache_max_entries_per_namespace}: precisa ser >= 1."
        )

    # Missao 44 - Diagnostico Automatico.
    if settings.diagnostics_disk_warning_free_mb < 1:
        issues.append(
            f"diagnostics_disk_warning_free_mb={settings.diagnostics_disk_warning_free_mb}: precisa ser >= 1."
        )
    if settings.diagnostics_disk_critical_free_mb < 1:
        issues.append(
            f"diagnostics_disk_critical_free_mb={settings.diagnostics_disk_critical_free_mb}: precisa ser >= 1."
        )
    if settings.diagnostics_disk_critical_free_mb >= settings.diagnostics_disk_warning_free_mb:
        issues.append(
            "diagnostics_disk_critical_free_mb "
            f"({settings.diagnostics_disk_critical_free_mb}) precisa ser menor que "
            f"diagnostics_disk_warning_free_mb ({settings.diagnostics_disk_warning_free_mb}): "
            "senao as faixas 'warning' e 'critical' colapsam em uma so."
        )

    # Missao 45 - Gerenciamento de Recursos.
    if settings.resource_job_retention_days < 1:
        issues.append(
            f"resource_job_retention_days={settings.resource_job_retention_days}: precisa ser >= 1."
        )

    # Missao 46 - Sistema de Alertas.
    if settings.alert_history_default_limit < 1:
        issues.append(
            f"alert_history_default_limit={settings.alert_history_default_limit}: precisa ser >= 1."
        )

    # Missao 47 - Testes de Recuperacao.
    if settings.recovery_max_jobs_per_sweep < 1:
        issues.append(
            f"recovery_max_jobs_per_sweep={settings.recovery_max_jobs_per_sweep}: precisa ser >= 1."
        )

    return issues


def validate_or_raise(settings: "Settings", environment: Environment) -> None:
    """Mesmo que validate_settings, mas levanta ConfigValidationError se
    houver qualquer problema E o perfil for production ou testing — os dois
    perfis onde uma configuração inválida tem maior chance de causar dano
    real (produção) ou mascarar um teste (testing). Para development/staging
    os problemas são retornados por validate_settings mas não interrompem o
    processo, para não travar o dia a dia de quem está só configurando algo."""

    issues = validate_settings(settings, environment)
    if issues and environment in (Environment.PRODUCTION, Environment.TESTING):
        raise ConfigValidationError(environment, issues)


def config_fingerprint(settings: "Settings") -> dict[str, object]:
    """Resumo versionado e estável da configuração ativa, útil para um
    endpoint de diagnóstico ou para comparar dois ambientes sem expor
    segredos. Nunca inclui valores de campos sensíveis (token/secret/key/password)."""

    sensitive_markers = ("token", "secret", "key", "password")
    field_names = sorted(type(settings).model_fields.keys())
    redacted = {
        name
        for name in field_names
        if any(marker in name for marker in sensitive_markers)
    }
    return {
        "config_schema_version": CONFIG_SCHEMA_VERSION,
        "environment": detect_environment().value,
        "total_fields": len(field_names),
        "redacted_fields": sorted(redacted),
    }
