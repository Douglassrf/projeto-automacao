"""Missao 49 - Auditoria de Dependencias.

Justificativa real (nao hipotetica): o `requirements.txt` deste
repositorio declara 19 dependencias (fastapi, uvicorn, sqlalchemy,
pydantic, pydantic-settings, PyJWT, passlib, bcrypt, python-dotenv,
python-multipart, email-validator, httpx, sentry-sdk, pillow,
python-magic, werkzeug, celery, requests, pytest) e **nenhuma** delas tem
versao fixa (`==`) - 19/19, 100%. Isso significa que um `pip install -r
requirements.txt` executado hoje e outro executado dentro de seis meses
podem instalar versoes completamente diferentes de qualquer uma dessas
bibliotecas, silenciosamente, sem nenhum aviso no proprio arquivo. Esse e
exatamente o tipo de "drift invisivel" que a Missao 48 (Documentacao
Viva) tratou para configuracao/rotas; esta missao trata o mesmo problema
para dependencias declaradas vs. instaladas.

`DependencyAuditService` le `requirements.txt` da raiz do repositorio em
tempo real (mesmo padrao de `_VERSION_FILE` usado por
`DocumentationService`), usa `packaging.requirements.Requirement` para
interpretar cada linha (em vez de um parser manual fragil) e compara cada
dependencia declarada com a versao de fato instalada no ambiente via
`importlib.metadata` - sem chamar nenhuma API externa, paga ou nao (nada
de PyPI Advisory DB / OSV / safety-db: o CLAUDE.md deste projeto proibe
servicos externos sem Douglas pedir, e nada nesta auditoria precisa de
rede para ser util).

Camada de seguranca: por padrao (`dependency_audit_warn_on_unpinned=True`)
toda dependencia sem versao fixa entra na lista de "issues" do snapshot,
nao so na lista bruta de dependencias - para nao deixar passar
silenciosamente o mesmo problema que motivou esta missao.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
from datetime import datetime, timezone

UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement

from app.core.config import Settings, get_settings
from app.core.config_profiles import detect_environment

_REQUIREMENTS_FILE = Path(__file__).resolve().parents[3] / "requirements.txt"


def _parse_requirements_text(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        try:
            req = Requirement(line)
        except InvalidRequirement as exc:
            entries.append(
                {
                    "raw": line,
                    "name": None,
                    "pinned": False,
                    "pinned_version": None,
                    "parse_error": str(exc),
                }
            )
            continue
        pinned_version = next(
            (spec.version for spec in req.specifier if spec.operator == "=="),
            None,
        )
        entries.append(
            {
                "raw": line,
                "name": req.name,
                "pinned": pinned_version is not None,
                "pinned_version": pinned_version,
                "parse_error": None,
            }
        )
    return entries


def _installed_version(name: str) -> str | None:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


class DependencyAuditService:
    """Missao 49 - Auditoria de Dependencias. Compara o que esta declarado
    em requirements.txt com o que esta de fato instalado no ambiente."""

    def __init__(self, settings: Settings | None = None, requirements_file: Path | None = None):
        self.settings = settings if settings is not None else get_settings()
        self.requirements_file = requirements_file if requirements_file is not None else _REQUIREMENTS_FILE

    def _read_requirements(self) -> list[dict[str, Any]]:
        try:
            text = self.requirements_file.read_text(encoding="utf-8")
        except OSError:
            return []
        return _parse_requirements_text(text)

    def audit(self) -> dict[str, Any]:
        warn_on_unpinned = self.settings.dependency_audit_warn_on_unpinned
        entries = self._read_requirements()

        dependencies: list[dict[str, Any]] = []
        issues: list[str] = []
        pinned_count = 0
        unpinned_count = 0
        missing_count = 0
        mismatch_count = 0

        for entry in entries:
            name = entry["name"]
            installed = _installed_version(name) if name else None
            pinned = entry["pinned"]
            missing = installed is None
            mismatch = bool(pinned and not missing and entry["pinned_version"] != installed)

            if pinned:
                pinned_count += 1
            else:
                unpinned_count += 1
            if missing:
                missing_count += 1
            if mismatch:
                mismatch_count += 1

            dependencies.append(
                {
                    "name": name,
                    "declared": entry["raw"],
                    "pinned": pinned,
                    "pinned_version": entry["pinned_version"],
                    "installed_version": installed,
                    "missing": missing,
                    "version_mismatch": mismatch,
                }
            )

            label = name or entry["raw"]
            if entry.get("parse_error"):
                issues.append(f"{label}: linha não reconhecida em requirements.txt ({entry['parse_error']}).")
                continue
            if missing:
                issues.append(f"{label}: declarado em requirements.txt mas não está instalado no ambiente atual.")
            if mismatch:
                issues.append(
                    f"{label}: requirements.txt fixa {entry['pinned_version']}, "
                    f"ambiente tem {installed} instalado."
                )
            if not pinned and warn_on_unpinned:
                issues.append(
                    f"{label}: sem versão fixa (==) em requirements.txt — uma instalação "
                    "futura pode trazer uma versão diferente sem aviso."
                )

        return {
            "generated_at": datetime.now(UTC),
            "requirements_file": str(self.requirements_file),
            "environment": detect_environment().value,
            "total_declared": len(dependencies),
            "pinned_count": pinned_count,
            "unpinned_count": unpinned_count,
            "missing_count": missing_count,
            "version_mismatch_count": mismatch_count,
            "issues": issues,
            "dependencies": sorted(dependencies, key=lambda item: (item["name"] or item["declared"])),
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        snap = snapshot if snapshot is not None else self.audit()
        lines: list[str] = []
        lines.append("# Auditoria de Dependencias - AdIntelligence Pro")
        lines.append("")
        lines.append(f"Gerado em: {snap['generated_at'].isoformat()}")
        lines.append(f"Arquivo: {snap['requirements_file']}")
        lines.append(f"Ambiente detectado: {snap['environment']}")
        lines.append("")
        lines.append(f"Total declarado: {snap['total_declared']}")
        lines.append(f"Fixados (==): {snap['pinned_count']}")
        lines.append(f"Sem versão fixa: {snap['unpinned_count']}")
        lines.append(f"Ausentes no ambiente: {snap['missing_count']}")
        lines.append(f"Divergência de versão: {snap['version_mismatch_count']}")
        lines.append("")
        if snap["issues"]:
            lines.append("## Problemas detectados agora")
            lines.append("")
            for issue in snap["issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("Nenhum problema detectado.")
        lines.append("")
        lines.append("## Dependências declaradas")
        lines.append("")
        lines.append("| Pacote | Declarado | Fixado | Instalado | Ausente | Divergente |")
        lines.append("|---|---|---|---|---|---|")
        for dep in snap["dependencies"]:
            lines.append(
                f"| `{dep['name']}` | `{dep['declared']}` | "
                f"{'sim' if dep['pinned'] else 'não'} | {dep['installed_version'] or '-'} | "
                f"{'sim' if dep['missing'] else 'não'} | {'sim' if dep['version_mismatch'] else 'não'} |"
            )
        lines.append("")
        return "\n".join(lines)
