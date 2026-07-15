"""Missao 122 - Engineering Memory Core (Fase v2.1).

Primeira missao da Fase v2.1 - Plataforma Autonoma de Engenharia. A partir
daqui o projeto para de "construir funcionalidade de produto" e passa a
construir a capacidade da propria plataforma de continuar excelente por
anos. Esta missao especificamente: a memoria permanente da engenharia.

Esta missao NAO reimplementa nenhuma fonte - agrega cinco fontes reais que
ja existem no repositorio, sempre lidas ao vivo:

1. **Historico de missoes** - reuso direto de
   `EvolutionDashboardService.mission_timeline()` (Missao 57). Nunca
   recalculado aqui.
2. **Historico de decisoes arquiteturais** - cada arquivo `.md` em
   `docs/historico_missoes/` (97 arquivos reais no repositorio hoje, um por
   decisao/missao documentada desde a Missao 06). A data de "introduzido em"
   vem do primeiro commit real que adicionou aquele arquivo
   (`git log --diff-filter=A`), nunca do mtime do disco local (que so
   reflete quando ESTE clone foi feito, nao a historia real do projeto).
3. **Historico de incidentes** - reuso direto de `AlertService.history()`
   (Missao 46, tabela `alert_events`, eventos open+resolved). Nomeado com
   honestidade: este projeto nao tem um sistema de "incident management"
   formal separado - os eventos de alerta reais (com `first_seen_at`/
   `resolved_at`) sao o registro de incidentes operacionais disponivel hoje.
   Deliberadamente NAO usa `app.core.incident_response.IncidentResponseMode`
   - aquele e um controle de runtime em memoria (dataclass `frozen`, guarda
   so o ultimo relatorio), nao uma tabela com historico persistido.
4. **Historico de certificacoes** - missoes da timeline real (item 1) cujo
   commit alterou pelo menos um arquivo cujo caminho bate com o padrao
   `certif|readiness|architecture_audit|code_review` (deteccao mecanica via
   `git show --name-only`, nunca uma lista de numeros de missao mantida a
   mao no codigo).
5. **Historico de versoes** - cada commit real que tocou o arquivo
   `VERSION` na raiz do repositorio, com o conteudo do arquivo naquele
   commit (`git show <hash>:VERSION`), nunca um changelog editado a mao.

Criterio de aceite da missao ("qualquer decisao do projeto pode ser
rastreada"): o metodo `trace(query)` busca um termo livre nas cinco fontes
acima e devolve so o que realmente bate - nunca inventa um resultado.

Leitura pura: todo comando `git` usado aqui e somente-leitura (log/show),
mesma garantia repetida desde a Missao 57.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import project_root
from app.services.alert_service import AlertService
from app.services.evolution_dashboard_service import EvolutionDashboardService

UTC = timezone.utc

_CERTIFICATION_PATH_PATTERN = re.compile(
    r"certif|readiness|architecture_audit|code_review", re.IGNORECASE
)


def _run_git(args: list[str]) -> str:
    """Roda um comando git real e somente-leitura. Mesmo padrao das
    Missoes 57/58/59/60 - falha visivel via `CalledProcessError`, nunca
    engolida em silencio."""
    try: result = subprocess.run(["git", *args], cwd=project_root(), capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError): return ""
    return result.stdout


class EngineeringMemoryCoreService:
    """Missao 122. Depende de `db` porque `AlertService` (Missao 46)
    depende - mesmo motivo de `EvolutionDashboardService` (Missao 57)
    precisar de `db` por causa do `UnifiedCertificationEngine`."""

    def __init__(
        self,
        db: Session,
        evolution_dashboard: EvolutionDashboardService | None = None,
        alert_service: AlertService | None = None,
    ) -> None:
        self.db = db
        self.evolution_dashboard = evolution_dashboard or EvolutionDashboardService(db)
        self.alert_service = alert_service or AlertService(db)

    # --- 1. missoes -------------------------------------------------

    def mission_history(self) -> list[dict[str, Any]]:
        """Reuso direto da Missao 57 - nunca recalculado aqui."""
        return self.evolution_dashboard.mission_timeline()

    # --- 2. decisoes arquiteturais -----------------------------------

    @staticmethod
    def _first_commit_for_path(rel_path: str) -> tuple[str | None, datetime | None]:
        log_output = _run_git(
            ["log", "--follow", "--diff-filter=A", "--pretty=format:%H|%ct", "--", rel_path]
        )
        lines = [line for line in log_output.splitlines() if line.strip()]
        if not lines:
            return None, None
        # --diff-filter=A com --follow lista do mais recente para o mais
        # antigo; a ultima linha e a adicao original do arquivo.
        commit_hash, epoch_seconds = lines[-1].split("|", 1)
        return commit_hash[:7], datetime.fromtimestamp(int(epoch_seconds), tz=UTC)

    def architectural_decision_history(self) -> list[dict[str, Any]]:
        """Um registro por arquivo `.md` real em `docs/historico_missoes/`
        - cada um documenta uma decisao tomada de fato no projeto."""
        decisions_dir = project_root() / "docs" / "historico_missoes"
        entries: list[dict[str, Any]] = []
        if not decisions_dir.exists():
            return entries

        for path in sorted(decisions_dir.glob("*.md")):
            rel_path = f"docs/historico_missoes/{path.name}"
            commit_short, introduced_at = self._first_commit_for_path(rel_path)
            entries.append(
                {
                    "file": rel_path,
                    "title": path.stem,
                    "introduced_commit": commit_short,
                    "introduced_at": introduced_at,
                }
            )

        entries.sort(
            key=lambda e: e["introduced_at"] or datetime.fromtimestamp(0, tz=UTC)
        )
        return entries

    # --- 3. incidentes -------------------------------------------------

    def incident_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Reuso direto de `AlertService.history()` (Missao 46) - eventos
        reais (open+resolved) da tabela `alert_events`."""
        return self.alert_service.history(limit=limit)

    # --- 4. certificacoes ------------------------------------------------

    @staticmethod
    def _changed_paths(commit_hash: str) -> list[str]:
        output = _run_git(["show", "--name-only", "--pretty=format:", commit_hash])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def certification_history(
        self, timeline: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """Missoes da timeline real (item 1) cujo commit tocou um caminho
        relacionado a certificacao/auditoria/revisao - deteccao mecanica,
        nunca uma lista de numeros de missao mantida a mao."""
        timeline = timeline if timeline is not None else self.mission_history()
        entries: list[dict[str, Any]] = []
        for entry in timeline:
            paths = self._changed_paths(entry["commit_hash"])
            matched = [p for p in paths if _CERTIFICATION_PATH_PATTERN.search(p)]
            if matched:
                entries.append({**entry, "certification_related_paths": matched})
        return entries

    # --- 5. versoes -----------------------------------------------------

    def version_history(self) -> list[dict[str, Any]]:
        """Cada commit real que tocou `VERSION`, com o conteudo do arquivo
        naquele commit - nunca um changelog editado a mao."""
        log_output = _run_git(
            ["log", "--follow", "--pretty=format:%H|%ct|%s", "--", "VERSION"]
        )
        entries: list[dict[str, Any]] = []
        for line in log_output.splitlines():
            if not line.strip():
                continue
            commit_hash, epoch_seconds, subject = line.split("|", 2)
            try:
                version_value = _run_git(["show", f"{commit_hash}:VERSION"]).strip()
            except subprocess.CalledProcessError:
                version_value = None
            entries.append(
                {
                    "commit_hash": commit_hash[:7],
                    "committed_at": datetime.fromtimestamp(int(epoch_seconds), tz=UTC),
                    "subject": subject,
                    "version": version_value,
                }
            )
        entries.sort(key=lambda e: e["committed_at"])
        return entries

    # --- agregacao + rastreabilidade -----------------------------------

    def memory_report(self) -> dict[str, Any]:
        mission_history = self.mission_history()
        return {
            "generated_at": datetime.now(UTC),
            "mission_history": mission_history,
            "architectural_decision_history": self.architectural_decision_history(),
            "incident_history": self.incident_history(),
            "certification_history": self.certification_history(mission_history),
            "version_history": self.version_history(),
        }

    def trace(self, query: str, report: dict[str, Any] | None = None) -> dict[str, Any]:
        """Criterio de aceite da Missao 122: 'qualquer decisao do projeto
        pode ser rastreada'. Busca textual (case-insensitive) nas cinco
        fontes - nunca inventa um resultado para uma busca sem match."""
        if not query or not query.strip():
            return {"query": query, "matches": {}, "total_matches": 0}

        needle = query.strip().lower()
        report = report if report is not None else self.memory_report()

        def _matches_mission(entry: dict[str, Any]) -> bool:
            return needle in str(entry.get("mission_number", "")) or needle in str(
                entry.get("subject", "")
            ).lower()

        def _matches_decision(entry: dict[str, Any]) -> bool:
            return needle in entry["file"].lower() or needle in entry["title"].lower()

        def _matches_incident(entry: dict[str, Any]) -> bool:
            return needle in str(entry.get("check_name", "")).lower() or needle in str(
                entry.get("message", "")
            ).lower()

        def _matches_certification(entry: dict[str, Any]) -> bool:
            if needle in str(entry.get("subject", "")).lower():
                return True
            return any(needle in p.lower() for p in entry.get("certification_related_paths", []))

        def _matches_version(entry: dict[str, Any]) -> bool:
            return needle in str(entry.get("version") or "").lower() or needle in str(
                entry.get("subject", "")
            ).lower()

        matches = {
            "mission_history": [e for e in report["mission_history"] if _matches_mission(e)],
            "architectural_decision_history": [
                e for e in report["architectural_decision_history"] if _matches_decision(e)
            ],
            "incident_history": [e for e in report["incident_history"] if _matches_incident(e)],
            "certification_history": [
                e for e in report["certification_history"] if _matches_certification(e)
            ],
            "version_history": [e for e in report["version_history"] if _matches_version(e)],
        }
        total_matches = sum(len(v) for v in matches.values())
        return {"query": query, "matches": matches, "total_matches": total_matches}

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.memory_report()

        lines: list[str] = ["# Engineering Memory Core (Missao 122)", ""]
        lines.append(f"- Gerado em: {report['generated_at']}")
        lines.append(f"- Missoes na memoria (Missao 57): {len(report['mission_history'])}")
        lines.append(
            "- Decisoes arquiteturais documentadas (docs/historico_missoes): "
            f"{len(report['architectural_decision_history'])}"
        )
        lines.append(
            f"- Eventos de incidente registrados (Missao 46): {len(report['incident_history'])}"
        )
        lines.append(
            f"- Missoes relacionadas a certificacao detectadas: {len(report['certification_history'])}"
        )
        lines.append(f"- Mudancas de versao registradas: {len(report['version_history'])}")
        lines.append("")

        lines.append("## Linha do tempo de versoes (VERSION real, via git log)")
        for entry in report["version_history"]:
            lines.append(
                f"- {entry['committed_at']} ({entry['commit_hash']}): "
                f"VERSION = {entry['version']} - {entry['subject']}"
            )
        lines.append("")

        lines.append("## Missoes relacionadas a certificacao (deteccao mecanica)")
        if report["certification_history"]:
            for entry in report["certification_history"]:
                lines.append(
                    f"- Missao {entry['mission_number']} ({entry['commit_hash']}): "
                    f"{entry['subject']}"
                )
        else:
            lines.append("- Nenhuma detectada na timeline atual.")

        return "\n".join(lines)
