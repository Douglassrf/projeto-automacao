"""Missao 48 - Documentacao Viva.

Justificativa real (nao hipotetica): o `README.md` deste repositorio afirma
hoje, em texto estatico, "Requer Python 3.11+" e "Ultima validacao
registrada... 261 passed". Nenhuma das duas frases reflete o estado atual:
o ambiente de execucao real e Python 3.10 (todo servico novo desde a Missao
41 carrega um comentario "compat Python 3.10" ao lado de `UTC =
timezone.utc`), e a suite de testes ja passou de 261 para 489 (Missoes
41-47). Documentacao escrita a mao e copiada para dentro de um `.md` fica
desatualizada no minuto em que o sistema muda - ninguem lembra de
sincronizar os dois lados.

`DocumentationService` resolve isso gerando a documentacao a partir do
estado *vivo* do sistema, a cada chamada, em vez de depender de um arquivo
estatico que alguem precisa lembrar de editar:

- Reaproveita `LOADED_ROUTES`/`FAILED_ROUTES`/`ROUTE_MODULES` de
  `app.api.safe_router` (mesmo padrao de import tardio com fallback usado
  por `observability.health_dashboard()`, Missao 27 - evita import
  circular, ja que `safe_router` importa modulos de rota que podem importar
  servicos).
- Reaproveita `CONFIG_SCHEMA_VERSION`, `detect_environment()` e
  `validate_settings()` (Missao 41) em vez de duplicar logica de
  ambiente/validacao.
- Le o arquivo `VERSION` da raiz do repositorio em tempo real (nao um
  numero copiado a mao em algum lugar).
- Enumera os campos de `Settings` via `model_fields` (introspeccao real do
  schema pydantic, nao uma lista mantida a mao que ficaria desatualizada a
  cada novo campo de configuracao).

Camada de seguranca: qualquer campo cujo nome contenha um marcador de
segredo (`secret`, `password`, `token`, `key`) e redigido por padrao
(`documentation_redact_secrets=True`) - o valor real nunca aparece no
snapshot nem no markdown gerado, apenas se o campo esta "configurado" (valor
diferente do default) ou nao.
"""

from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

# Marcadores de nome de campo tratados como segredo. Casamento por
# substring (case-insensitive) de proposito: cobre tanto
# "jwt_secret_key" quanto "default_admin_password" quanto
# "huggingface_token" quanto "openai_api_key" sem precisar manter uma
# lista exaustiva de nomes exatos que ficaria desatualizada a cada novo
# campo (mesmo principio "vivo" do resto desta missao).
_SECRET_FIELD_MARKERS = ("secret", "password", "token", "key")

_REDACTED_PLACEHOLDER = "***redacted***"

# VERSION fica na raiz do repositorio. Este arquivo vive em
# src/app/services/documentation_service.py -> parents[3] e a raiz
# (mesma estrutura preservada dentro do container Docker via `COPY . .`).
_VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"


def _is_secret_field(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in _SECRET_FIELD_MARKERS)


def _read_version_file() -> str | None:
    try:
        content = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return content or None


class DocumentationService:
    """Missao 48 - Documentacao Viva. Gera snapshots de documentacao a
    partir do estado real do sistema em tempo de execucao."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings if settings is not None else get_settings()

    def routes_summary(self) -> dict[str, Any]:
        """Reaproveita o estado real de carregamento de rotas do
        safe_router (mesmo dado que alimenta /api/v1/diagnostics/routes e
        observability.health_dashboard()), em vez de manter uma lista de
        rotas documentada a mao."""

        try:
            from app.api.safe_router import FAILED_ROUTES, LOADED_ROUTES, ROUTE_MODULES
        except Exception:
            FAILED_ROUTES, LOADED_ROUTES, ROUTE_MODULES = [], [], []

        return {
            "declared": len(ROUTE_MODULES),
            "loaded": len(LOADED_ROUTES),
            "failed": len(FAILED_ROUTES),
            "loaded_modules": sorted(LOADED_ROUTES),
            "failed_details": FAILED_ROUTES,
        }

    def settings_summary(self) -> list[dict[str, Any]]:
        """Introspeccao real do schema de `Settings` (model_fields), nao
        uma lista mantida a mao. Campos identificados como segredo (ver
        `_is_secret_field`) tem o valor redigido quando
        `documentation_redact_secrets=True` (padrao)."""

        redact = self.settings.documentation_redact_secrets
        fields: list[dict[str, Any]] = []
        for name, field_info in type(self.settings).model_fields.items():
            value = getattr(self.settings, name)
            secret = _is_secret_field(name)
            default = field_info.default
            configured = value != default
            if secret and redact:
                shown_value = _REDACTED_PLACEHOLDER if value not in (None, "") else None
            else:
                shown_value = value if value is None else str(value)
            fields.append(
                {
                    "name": name,
                    "type": str(field_info.annotation),
                    "secret": secret,
                    "configured": configured,
                    "value": shown_value,
                }
            )
        return sorted(fields, key=lambda item: item["name"])

    def live_snapshot(self) -> dict[str, Any]:
        """Snapshot completo, calculado agora - nunca um arquivo .md
        estatico que alguem esqueceu de atualizar."""

        environment = detect_environment()
        issues = validate_settings(self.settings, environment)
        settings_fields = self.settings_summary()
        return {
            "generated_at": datetime.now(UTC),
            "version_file": _read_version_file(),
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "environment": environment.value,
            "routes": self.routes_summary(),
            "settings_field_count": len(settings_fields),
            "settings_issues": issues,
            "settings_fields": settings_fields,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        """Renderiza o snapshot como Markdown legivel - o documento em si
        e o produto desta missao, gerado fresco a cada chamada."""

        snap = snapshot if snapshot is not None else self.live_snapshot()
        routes = snap["routes"]
        lines: list[str] = []
        lines.append("# Documentacao Viva - AdIntelligence Pro")
        lines.append("")
        lines.append(f"Gerado em: {snap['generated_at'].isoformat()}")
        lines.append(f"Versao do app (arquivo VERSION): {snap['version_file'] or 'desconhecida'}")
        lines.append(f"Esquema de configuracao: {snap['config_schema_version']}")
        lines.append(f"Ambiente detectado: {snap['environment']}")
        lines.append("")
        lines.append("## Rotas")
        lines.append("")
        lines.append(f"- Declaradas: {routes['declared']}")
        lines.append(f"- Carregadas: {routes['loaded']}")
        lines.append(f"- Falharam: {routes['failed']}")
        if routes["failed_details"]:
            lines.append("")
            lines.append("### Rotas com falha de carregamento")
            for item in routes["failed_details"]:
                lines.append(f"- `{item.get('module')}`: {item.get('error')}")
        lines.append("")
        lines.append("## Configuracao")
        lines.append("")
        lines.append(f"Total de campos: {snap['settings_field_count']}")
        if snap["settings_issues"]:
            lines.append("")
            lines.append("### Problemas de validacao detectados agora")
            for issue in snap["settings_issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("")
            lines.append("Nenhum problema de validacao detectado para o ambiente atual.")
        lines.append("")
        lines.append("### Campos configurados (valores de segredo redigidos)")
        lines.append("")
        lines.append("| Campo | Tipo | Segredo | Configurado | Valor |")
        lines.append("|---|---|---|---|---|")
        for field in snap["settings_fields"]:
            value = field["value"] if field["value"] is not None else "-"
            lines.append(
                f"| `{field['name']}` | {field['type']} | "
                f"{'sim' if field['secret'] else 'nao'} | "
                f"{'sim' if field['configured'] else 'nao'} | {value} |"
            )
        lines.append("")
        return "\n".join(lines)
