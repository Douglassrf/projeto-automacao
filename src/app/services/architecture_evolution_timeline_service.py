"""Missao 123 - Architecture Evolution Timeline (Fase v2.1).

Segunda missao da Fase v2.1. Constroi a linha do tempo oficial da
arquitetura em cinco dimensoes, todas mineradas ao vivo do git real -
nenhuma e reimplementada de uma fonte que ja existe:

1. **Evolucao dos modulos** - cada arquivo `.py` em `src/app/core/`
   (a camada de infraestrutura do projeto: config, container de DI,
   diagnostico, etc.), com primeiro commit, ultimo commit e total de
   commits reais.
2. **Evolucao das APIs** - mesma analise para `src/app/api/routes/`
   (cada arquivo de rota e literalmente uma API exposta).
3. **Evolucao das configuracoes** - historico de
   `CONFIG_SCHEMA_VERSION` em `src/app/core/config_profiles.py`,
   minerado commit a commit (mesma tecnica de `VERSION` da Missao 122).
4. **Evolucao das certificacoes** - reuso direto de
   `EngineeringMemoryCoreService.certification_history()` (Missao 122).
   Nao recalculado aqui.
5. **Evolucao dos servicos** - mesma analise de (1)/(2) para
   `src/app/services/`.

Otimizacao deliberada: em vez de um `git log` por arquivo (o que
faria ~170 chamadas de subprocesso so para modulos+APIs+servicos),
cada dimensao de diretorio faz UMA unica chamada
`git log --name-only -- <diretorio>` e associa commits a arquivos no
parsing - mesmos dados reais, ordem de grandeza mais rapido. Isso e
relevante porque o ambiente de sandbox deste projeto tem custo de
processo variável; menos chamadas de subprocesso = menos risco de
timeout, sem abrir mao de nenhuma garantia de veracidade.

Eixo informativo (nunca bloqueante): `files_without_history` em cada
dimensao de diretorio - arquivos presentes no disco hoje sem nenhum
commit encontrado (renomes que o git não conseguiu seguir, por
exemplo). Documentado, nunca escondido.

Criterio da missao ("toda mudanca possui historico tecnico"):
`render_markdown()` e `evolution_report()` tornam essa cobertura
visivel; se `files_without_history` aparecer no relatorio, e um gap
real, nao um veredito decorativo de "tudo certo".
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import project_root
from app.services.engineering_memory_core_service import EngineeringMemoryCoreService

UTC = timezone.utc

_COMMIT_HEADER_PATTERN = re.compile(r"^([0-9a-f]{40})\|(\d+)\|(.*)$")
_CONFIG_SCHEMA_VERSION_PATTERN = re.compile(
    r'^CONFIG_SCHEMA_VERSION\s*=\s*"([^"]+)"', re.MULTILINE
)

_CONFIG_PROFILES_PATH = "src/app/core/config_profiles.py"


def _run_git(args: list[str]) -> str:
    """Comando git real, somente-leitura - mesmo padrao das Missoes
    57/58/59/60/122."""
    result = subprocess.run(
        ["git", *args],
        cwd=project_root(),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


class ArchitectureEvolutionTimelineService:
    """Missao 123. Depende de `db` porque
    `EngineeringMemoryCoreService` (Missao 122) depende - mesmo motivo
    em cascata desde a Missao 46/57."""

    def __init__(
        self,
        db: Session,
        engineering_memory: EngineeringMemoryCoreService | None = None,
    ) -> None:
        self.db = db
        self.engineering_memory = engineering_memory or EngineeringMemoryCoreService(db)

    # --- mineracao de diretorio (modulos / APIs / servicos) -----------

    @staticmethod
    def _directory_history(rel_dir: str) -> dict[str, list[dict[str, Any]]]:
        """Uma unica chamada `git log --name-only` para todo o
        diretorio - associa cada commit aos arquivos que ele alterou
        dentro dele, sem uma chamada de subprocesso por arquivo.

        Cada commit recebe um indice `_order` sequencial (0 = mais
        recente, crescente para tras) na ordem em que o git o emite.
        Isso e usado como criterio de ordenacao em vez do timestamp de
        segundo (`%ct`) puro, porque commits no mesmo segundo sao
        comuns (pipelines automatizados, ou os proprios testes desta
        suite) e o timestamp por si so nao desempata - a ordem de
        travessia do git (topologica + data) e a fonte de verdade real
        e nunca tem ambiguidade dentro do mesmo `git log`."""
        output = _run_git(["log", "--pretty=format:%H|%ct|%s", "--name-only", "--", rel_dir])
        by_file: dict[str, list[dict[str, Any]]] = {}
        current_commit: dict[str, Any] | None = None
        order = 0
        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue
            match = _COMMIT_HEADER_PATTERN.match(line)
            if match:
                commit_hash, epoch_seconds, subject = match.groups()
                current_commit = {
                    "commit_hash": commit_hash[:7],
                    "committed_at": datetime.fromtimestamp(int(epoch_seconds), tz=UTC),
                    "subject": subject,
                    "_order": order,
                }
                order += 1
                continue
            if current_commit is not None:
                by_file.setdefault(line, []).append(current_commit)
        return by_file

    def _directory_evolution(self, rel_dir: str) -> dict[str, Any]:
        directory = project_root() / rel_dir
        files_on_disk: set[str] = set()
        if directory.exists():
            for path in sorted(directory.glob("*.py")):
                if path.name == "__init__.py":
                    continue
                files_on_disk.add(path.relative_to(project_root()).as_posix())

        history_by_file = self._directory_history(rel_dir) if files_on_disk else {}

        def _strip_order(commit: dict[str, Any]) -> dict[str, Any]:
            return {k: v for k, v in commit.items() if k != "_order"}

        entries: list[dict[str, Any]] = []
        for rel_path in sorted(files_on_disk):
            commits = sorted(history_by_file.get(rel_path, []), key=lambda c: c["_order"])
            if not commits:
                continue
            # _order 0 = mais recente; o maior _order da lista e o commit mais antigo (primeiro de fato)
            oldest, newest = commits[-1], commits[0]
            entries.append(
                {
                    "file": rel_path,
                    "first_commit": _strip_order(oldest),
                    "last_commit": _strip_order(newest),
                    "total_commits": len(commits),
                    "_first_order": oldest["_order"],
                }
            )
        # maior _order do primeiro commit = introduzido mais cedo na historia real -> vem primeiro
        entries.sort(key=lambda e: e["_first_order"], reverse=True)
        for entry in entries:
            del entry["_first_order"]

        files_without_history = sorted(files_on_disk - {e["file"] for e in entries})
        return {"files": entries, "files_without_history": files_without_history}

    def module_evolution(self) -> dict[str, Any]:
        """Evolucao dos modulos: src/app/core/ (camada de
        infraestrutura - config, DI, diagnostico, etc.)."""
        return self._directory_evolution("src/app/core")

    def api_evolution(self) -> dict[str, Any]:
        """Evolucao das APIs: src/app/api/routes/ (cada arquivo e uma
        API exposta de fato)."""
        return self._directory_evolution("src/app/api/routes")

    def service_evolution(self) -> dict[str, Any]:
        """Evolucao dos servicos: src/app/services/."""
        return self._directory_evolution("src/app/services")

    # --- configuracoes ---------------------------------------------------

    def configuration_evolution(self) -> list[dict[str, Any]]:
        """Historico real de CONFIG_SCHEMA_VERSION em
        config_profiles.py - mesma tecnica de mineracao de VERSION da
        Missao 122, aplicada a uma constante dentro de um arquivo em
        vez do conteudo inteiro do arquivo."""
        log_output = _run_git(
            ["log", "--follow", "--pretty=format:%H|%ct|%s", "--", _CONFIG_PROFILES_PATH]
        )
        entries: list[dict[str, Any]] = []
        for line in log_output.splitlines():
            if not line.strip():
                continue
            commit_hash, epoch_seconds, subject = line.split("|", 2)
            schema_version = None
            try:
                content = _run_git(["show", f"{commit_hash}:{_CONFIG_PROFILES_PATH}"])
                match = _CONFIG_SCHEMA_VERSION_PATTERN.search(content)
                if match:
                    schema_version = match.group(1)
            except subprocess.CalledProcessError:
                schema_version = None
            entries.append(
                {
                    "commit_hash": commit_hash[:7],
                    "committed_at": datetime.fromtimestamp(int(epoch_seconds), tz=UTC),
                    "subject": subject,
                    "config_schema_version": schema_version,
                }
            )
        # git log emite do mais novo para o mais antigo; invertendo obtemos a
        # ordem cronologica real sem depender da resolucao de segundo do
        # timestamp (mesmo motivo documentado em `_directory_history`).
        entries.reverse()
        return entries

    # --- certificacoes (reuso direto da Missao 122) -----------------------

    def certification_evolution(self) -> list[dict[str, Any]]:
        """Reuso direto de EngineeringMemoryCoreService.certification_history()
        (Missao 122) - nunca recalculado aqui."""
        return self.engineering_memory.certification_history()

    # --- agregacao -----------------------------------------------------

    def evolution_report(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(UTC),
            "module_evolution": self.module_evolution(),
            "api_evolution": self.api_evolution(),
            "configuration_evolution": self.configuration_evolution(),
            "certification_evolution": self.certification_evolution(),
            "service_evolution": self.service_evolution(),
        }

    @staticmethod
    def _gap_count(report: dict[str, Any]) -> int:
        total = 0
        for key in ("module_evolution", "api_evolution", "service_evolution"):
            total += len(report[key]["files_without_history"])
        return total

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.evolution_report()

        lines: list[str] = ["# Architecture Evolution Timeline (Missao 123)", ""]
        lines.append(f"- Gerado em: {report['generated_at']}")
        lines.append(f"- Modulos rastreados (src/app/core): {len(report['module_evolution']['files'])}")
        lines.append(f"- APIs rastreadas (src/app/api/routes): {len(report['api_evolution']['files'])}")
        lines.append(f"- Servicos rastreados (src/app/services): {len(report['service_evolution']['files'])}")
        lines.append(
            f"- Mudancas de CONFIG_SCHEMA_VERSION registradas: {len(report['configuration_evolution'])}"
        )
        lines.append(
            f"- Missoes relacionadas a certificacao (Missao 122): {len(report['certification_evolution'])}"
        )

        gap_count = self._gap_count(report)
        if gap_count:
            lines.append(
                f"- **Atencao:** {gap_count} arquivo(s) no disco sem historico de git "
                "encontrado (eixo informativo, nao bloqueia o relatorio)."
            )
        else:
            lines.append("- Nenhum arquivo sem historico de git encontrado nas tres dimensoes de diretorio.")
        lines.append("")

        lines.append("## Evolucao das configuracoes (CONFIG_SCHEMA_VERSION real, via git)")
        for entry in report["configuration_evolution"]:
            lines.append(
                f"- {entry['committed_at']} ({entry['commit_hash']}): "
                f"CONFIG_SCHEMA_VERSION = {entry['config_schema_version']} - {entry['subject']}"
            )

        return "\n".join(lines)
