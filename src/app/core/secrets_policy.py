from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SecretSeverity(StrEnum):
    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"


SENSITIVE_KEYS = frozenset(
    {
        "JWT_SECRET_KEY",
        "DEFAULT_ADMIN_PASSWORD",
        "META_ACCESS_TOKEN",
        "OPENAI_API_KEY",
        "GOOGLE_GEMINI_API_KEY",
        "ELEVENLABS_API_KEY",
        "HUGGINGFACE_TOKEN",
        "GITHUB_TOKEN",
        "VERCEL_TOKEN",
        "NETLIFY_TOKEN",
        "N8N_WEBHOOK_SECRET",
        "AFFILIATE_API_SECRET",
        "SENTRY_DSN",
    }
)

WEAK_SECRET_VALUES = frozenset(
    {
        "",
        "change-me",
        "change-me-local-dev-only",
        "change-me-super-secret-local-key",
        "troque-esta-senha-em-producao",
        "admin12345",
        "password",
        "secret",
        "test",
        "demo",
    }
)


@dataclass(frozen=True)
class SecretCheck:
    key: str
    configured: bool
    severity: SecretSeverity
    message: str
    masked_value: str


class SecretsPolicy:
    def __init__(self, sensitive_keys: frozenset[str] = SENSITIVE_KEYS) -> None:
        self.sensitive_keys = sensitive_keys

    def mask(self, value: str | None) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    def check(self, key: str, value: str | None, *, production: bool = False) -> SecretCheck:
        normalized_key = key.upper()
        normalized_value = (value or "").strip()
        is_sensitive = normalized_key in self.sensitive_keys or any(marker in normalized_key for marker in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))
        configured = bool(normalized_value)

        if not is_sensitive:
            return SecretCheck(normalized_key, configured, SecretSeverity.OK, "Chave nao sensivel.", self.mask(normalized_value))

        if not configured:
            severity = SecretSeverity.BLOCKED if production else SecretSeverity.WARNING
            return SecretCheck(normalized_key, False, severity, "Segredo ausente.", "")

        if normalized_value.lower() in WEAK_SECRET_VALUES or len(normalized_value) < 16:
            severity = SecretSeverity.BLOCKED if production else SecretSeverity.WARNING
            return SecretCheck(normalized_key, True, severity, "Segredo fraco ou valor padrao.", self.mask(normalized_value))

        return SecretCheck(normalized_key, True, SecretSeverity.OK, "Segredo configurado sem exposicao.", self.mask(normalized_value))

    def audit_mapping(self, values: dict[str, str | None], *, production: bool = False) -> dict[str, object]:
        checks = [self.check(key, value, production=production) for key, value in sorted(values.items())]
        blocked = [check for check in checks if check.severity == SecretSeverity.BLOCKED]
        warnings = [check for check in checks if check.severity == SecretSeverity.WARNING]
        return {
            "production": production,
            "total": len(checks),
            "blocked": len(blocked),
            "warnings": len(warnings),
            "ok": len(checks) - len(blocked) - len(warnings),
            "checks": [check.__dict__ | {"severity": check.severity.value} for check in checks],
            "safe_to_start_real_mode": production and not blocked,
        }


def known_sensitive_keys() -> list[str]:
    return sorted(SENSITIVE_KEYS)

