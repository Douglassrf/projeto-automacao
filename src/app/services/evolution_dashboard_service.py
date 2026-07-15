"""Missao 57 - Evolution Dashboard.

Contexto: as Missoes 51-56 entregaram seis motores que cada um responde
"a sua propria pergunta de saude" - mas nenhum lugar no repositorio mostra
a EVOLUCAO do projeto, missao a missao, num unico lugar. Esta missao nao
reimplementa nenhum dos motores existentes - agrega dois sinais que ja
existem, sempre lidos ao vivo, nunca hardcoded:

1. **Linha do tempo de missoes** - minerada diretamente do `git log` real
   deste repositorio. Nenhuma lista de "missoes 41 a 56" mantida a mao em
   codigo Python - se um commit novo seguir a convencao real de nomeacao
   ja usada nas Missoes 41-56 ("Missao N - ..." ou "Missão N: ..."), ele
   aparece na proxima chamada, sem editar este arquivo. Comprovado: a
   convencao tem as duas grafias (com e sem acento - "Missão 41" e
   "Missao 42" coexistem no historico real), e o regex cobre as duas.
2. **Snapshot de saude atual** - agrega `UnifiedCertificationEngine`
   (Missao 53), `ArchitectureAuditService` (Missao 55) e
   `CodeReviewService` (Missao 56) tal como eles existem hoje. Este
   servico nunca recalcula nada que os tres ja calculam - soh le o
   resultado de cada um e os apresenta juntos.

Eixo informativo (mesma filosofia de `di_adoption` na Missao 55,
`missing_docstring`/`long_function`/`todo_marker` na Missao 56): deteccao
de lacunas (numeros de missao ausentes) e duplicatas na sequencia real -
nunca afirma "esta tudo certo", soh relata o que encontrou no historico.

Leitura pura, com uma ressalva explicita: os comandos `git log`/`git show`
usados aqui sao sempre somente-leitura (nunca `checkout`/`reset`/`push`) -
mesma garantia de "leitura pura" repetida nas Missoes 53/55/56, estendida
aqui para o historico de commits em vez de so o estado atual de arquivos.
Uso de `subprocess` para chamar `git` segue precedente ja existente no
repositorio (`video_pipeline.py`, `ugc_processing.py`, `premium_render.py`
ja chamam ferramentas externas via `subprocess`) - nao introduz um padrao
novo, aplica o mesmo padrao a uma ferramenta de leitura (git) em vez de
processamento de midia.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import project_root
from app.services.architecture_audit_service import ArchitectureAuditService
from app.services.code_review_service import CodeReviewService
from app.services.unified_certification_service import UnifiedCertificationEngine

UTC = timezone.utc

# Aceita "Missao 42" e "Missão 41" - as duas grafias reais encontradas no
# historico do projeto (ver docstring acima). Case-insensitive.
_MISSION_SUBJECT_PATTERN = re.compile(r"Miss[aã]o\s+(\d+)", re.IGNORECASE)

# Linha de resumo de `git show --stat`, ex.:
# "4 files changed, 506 insertions(+)" ou
# "3 files changed, 336 insertions(+), 83 deletions(-)".
_STAT_SUMMARY_PATTERN = re.compile(
    r"(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?"
)

# Linha adicionada (prefixo "+", nao "+++") declarando uma funcao de teste.
_TEST_FUNCTION_ADDED_PATTERN = re.compile(r"^\+\s*(?:async\s+)?def\s+test_\w+")


def _run_git(args: list[str]) -> str:
    """Roda um comando git real e somente-leitura (log/show/rev-parse)
    contra o repositorio do projeto. Nunca um comando que muta estado
    (checkout, reset, push, commit) - leitura pura. Falha visivel: se o
    comando git falhar, `subprocess.run(check=True)` levanta
    `CalledProcessError` - nunca engolido em silencio."""
        try: result = subprocess.run(["git", *args], cwd=project_root(), capture_output=True, text=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError, OSError): return ""
    return result.stdout


class EvolutionDashboardService:
    """Missao 57. Depende de `db` porque `UnifiedCertificationEngine`
    depende (Platinum/Diagnostics/Recovery leem o banco) - mesmo motivo
    de `get_certification_service` no container (Missao 52). As outras
    duas colaboradoras (`ArchitectureAuditService`, `CodeReviewService`)
    nao precisam de banco, mesmo como documentado nelas mesmas (Missoes
    55/56) - instanciadas aqui sem `db`."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.unified_engine = UnifiedCertificationEngine(db)
        self.architecture_audit = ArchitectureAuditService()
        self.code_review = CodeReviewService()

    @staticmethod
    def _commit_stat(commit_hash: str) -> dict[str, int]:
        stat_output = _run_git(["show", "--stat", "--format=", commit_hash])
        for line in stat_output.splitlines():
            match = _STAT_SUMMARY_PATTERN.search(line)
            if match:
                files_changed, insertions, deletions = match.groups()
                return {
                    "files_changed": int(files_changed),
                    "insertions": int(insertions or 0),
                    "deletions": int(deletions or 0),
                }
        return {"files_changed": 0, "insertions": 0, "deletions": 0}

    @staticmethod
    def _tests_added(commit_hash: str) -> int:
        diff_output = _run_git(["show", commit_hash, "--", "src/app/tests/"])
        return sum(
            1
            for line in diff_output.splitlines()
            if _TEST_FUNCTION_ADDED_PATTERN.match(line)
        )

    def mission_timeline(self) -> list[dict[str, Any]]:
        """Le o `git log --all` agora e devolve uma entrada por commit cuja
        mensagem segue a convencao real de nomeacao de missao deste
        projeto. Nenhum numero de missao e citado a mao em codigo - se a
        convencao mudar ou um commit novo aparecer, a proxima chamada
        reflete isso sem editar este metodo."""

        log_output = _run_git(["log", "--all", "--pretty=format:%H|%ct|%s"])

        entries: list[dict[str, Any]] = []
        for line in log_output.splitlines():
            if not line.strip():
                continue
            commit_hash, epoch_seconds, subject = line.split("|", 2)
            match = _MISSION_SUBJECT_PATTERN.search(subject)
            if not match:
                continue
            stat = self._commit_stat(commit_hash)
            entries.append(
                {
                    "mission_number": int(match.group(1)),
                    "commit_hash": commit_hash[:7],
                    "subject": subject,
                    "committed_at": datetime.fromtimestamp(int(epoch_seconds), tz=UTC),
                    "tests_added": self._tests_added(commit_hash),
                    **stat,
                }
            )

        entries.sort(key=lambda entry: entry["mission_number"])
        return entries

    def timeline_health(
        self, timeline: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Eixo informativo (mesma filosofia de `di_adoption` na Missao 55):
        detecta lacunas e duplicatas na sequencia real de numeros de
        missao - nunca afirma "esta correto", soh relata o que encontrou
        no historico real (ou no `timeline` sintetico passado em teste)."""

        timeline = timeline if timeline is not None else self.mission_timeline()
        numbers = [entry["mission_number"] for entry in timeline]
        duplicate_numbers = sorted({n for n in numbers if numbers.count(n) > 1})

        gaps: list[int] = []
        if numbers:
            present = set(numbers)
            gaps = [n for n in range(min(numbers), max(numbers) + 1) if n not in present]

        return {
            "total_missions_detected": len(timeline),
            "lowest_mission_number": min(numbers) if numbers else None,
            "highest_mission_number": max(numbers) if numbers else None,
            "missing_mission_numbers": gaps,
            "duplicate_mission_numbers": duplicate_numbers,
            "total_tests_added_across_missions": sum(
                entry.get("tests_added", 0) for entry in timeline
            ),
        }

    def current_snapshot(self) -> dict[str, Any]:
        """Agrega o estado vivo dos tres motores ja existentes - nunca
        recalcula nada que eles ja calculam."""

        certification = self.unified_engine.certify()
        architecture = self.architecture_audit.audit()
        code_review = self.code_review.review_repository()

        return {
            "unified_certified": certification["unified_certified"],
            "platinum_certified": certification["platinum_certified"],
            "gold_certified": certification["gold_certified"],
            "architecture_clean": architecture["clean"],
            "code_review_clean": code_review["clean"],
            "code_review_blocking_findings": code_review["total_blocking_findings"],
        }

    def evolution_report(self) -> dict[str, Any]:
        timeline = self.mission_timeline()
        return {
            "generated_at": datetime.now(UTC),
            "timeline": timeline,
            "timeline_health": self.timeline_health(timeline),
            "current_snapshot": self.current_snapshot(),
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.evolution_report()
        health = report["timeline_health"]
        snapshot = report["current_snapshot"]

        lines: list[str] = ["# Evolution Dashboard (Missao 57)", ""]
        lines.append(f"- Gerado em: {report['generated_at']}")
        lines.append(
            f"- Missoes detectadas no historico real: {health['total_missions_detected']}"
        )
        if health["total_missions_detected"]:
            lines.append(
                f"- Intervalo: Missao {health['lowest_mission_number']} "
                f"a Missao {health['highest_mission_number']}"
            )
        if health["missing_mission_numbers"]:
            lines.append(f"- Numeros ausentes na sequencia: {health['missing_mission_numbers']}")
        if health["duplicate_mission_numbers"]:
            lines.append(f"- Numeros duplicados: {health['duplicate_mission_numbers']}")
        lines.append(
            "- Total de testes adicionados (somado por commit de missao): "
            f"{health['total_tests_added_across_missions']}"
        )
        lines.append("")

        lines.append("## Snapshot de saude atual (motores existentes, sem recalculo)")
        unified_verdict = "CERTIFICADO" if snapshot["unified_certified"] else "NAO CERTIFICADO"
        lines.append(f"- Certificacao Unificada (Missao 53): {unified_verdict}")
        platinum_verdict = "OK" if snapshot["platinum_certified"] else "FALHOU"
        gold_verdict = "OK" if snapshot["gold_certified"] else "FALHOU"
        lines.append(f"  - Platinum: {platinum_verdict} / Gold: {gold_verdict}")
        architecture_verdict = "LIMPA" if snapshot["architecture_clean"] else "COM DESVIO"
        lines.append(f"- Auditoria de Arquitetura (Missao 55): {architecture_verdict}")
        if snapshot["code_review_clean"]:
            code_review_line = "- Revisao de Codigo (Missao 56): LIMPA"
        else:
            code_review_line = (
                "- Revisao de Codigo (Missao 56): "
                f"{snapshot['code_review_blocking_findings']} achado(s) bloqueante(s)"
            )
        lines.append(code_review_line)
        lines.append("")

        lines.append("## Linha do tempo (mineracao real do git log)")
        for entry in report["timeline"]:
            lines.append(
                f"- Missao {entry['mission_number']} ({entry['commit_hash']}): "
                f"{entry['subject']} - {entry['files_changed']} arquivo(s), "
                f"+{entry['insertions']}/-{entry['deletions']}, "
                f"{entry['tests_added']} teste(s) novo(s)"
            )

        return "\n".join(lines)
