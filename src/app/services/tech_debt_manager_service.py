"""Missao 58 - Automatic Technical Debt Manager.

Contexto: a Missao 56 (`CodeReviewService`) ja detecta divida tecnica via
AST - `missing_docstring`, `long_function`, `todo_marker` (os tres eixos
informativos, nunca bloqueantes). O que faltava era *gerenciar* essa
lista: hoje sao centenas de achados sem nenhuma ordem entre si. Esta
missao nao reimplementa a deteccao (reusa `CodeReviewService.
review_repository()` sem recalcular nada por conta propria, mesmo padrao
agregador da Missao 57) - acrescenta uma dimensao nova: idade real de
cada arquivo com divida, via `git log`, para transformar a lista plana
num backlog priorizado.

Decisao de performance (documentada por transparencia): a primeira versao
desta missao calculava idade por **linha exata** via `git log -L
<linha>:<arquivo>` para cada um dos ~590 achados informativos do
repositorio real - e isso significava ~590 subprocessos `git` separados,
cada um fazendo um historico de conteudo de linha (mais caro que um
`git log` comum). Medido directamente: o calculo completo nao terminou
nem em 40s. Trocado por uma unica chamada de `git log --name-only` para
todo o historico (~0.03s reais, medido), construindo um mapa
`arquivo -> idade em dias` de uma vez so - depois cada achado so faz uma
busca O(1) nesse mapa, nunca um subprocesso por achado. Perde precisao de
linha exata (a idade agora e "desde quando este *arquivo* nao e tocado",
nao "esta *linha* exata") mas continua sendo dado real do git, nunca
inventado - e o ganho de desempenho e de ~3 ordens de magnitude.

"Automatic" aqui significa o mesmo que nas Missoes 55/56: nenhuma chamada
de API de LLM paga (regra 6 do CLAUDE.md) - priorizacao deterministica por
peso de regra x idade real em dias, sempre recalculada ao vivo (nunca um
snapshot congelado), mesmo principio "continuo" repetido desde a Missao
55.

Importante: este servico **nao certifica nada** e **nao participa de
nenhum veredito existente** (Platinum/Gold/Unified/architecture/code-
review). E uma ferramenta de gestao de backlog, deliberadamente sem campo
`clean` - diferente de todos os outros services desta serie. Mesmo
principio de leitura pura ja documentado em `ArchitectureAuditService` e
`CodeReviewService`: nenhum metodo aqui escreve em disco, no git ou no
banco - so le.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from typing import Any

from app.core.config import project_root
from app.services.code_review_service import CodeReviewService

UTC = timezone.utc

_APP_PATHSPEC = "src/app/"

# Peso por regra: todo_marker e a promessa mais explicita ja quebrada
# ("isto devia ter sido feito"), por isso pesa mais que long_function
# (debito estrutural, sem urgencia declarada) e missing_docstring (debito
# de clareza, o mais barato de resolver).
_RULE_WEIGHT: dict[str, int] = {
    "todo_marker": 3,
    "long_function": 2,
    "missing_docstring": 1,
}

_DEBT_RULES = frozenset(_RULE_WEIGHT)


def _run_git(args: list[str]) -> str:
    try: result = subprocess.run(["git", *args], cwd=project_root(), capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError): return ""
    return result.stdout


class TechDebtManagerService:
    """Missao 58. Le-only, sem `db` no construtor - mesmo motivo
    documentado em `ArchitectureAuditService` (Missao 55) e
    `CodeReviewService` (Missao 56): nenhum eixo aqui depende do banco,
    so de `CodeReviewService` (arquivo) e do `git` (historico)."""

    def __init__(self, code_review: CodeReviewService | None = None) -> None:
        self.code_review = code_review or CodeReviewService()

    @staticmethod
    def _file_age_days_map() -> dict[str, int]:
        """Mapa `{caminho relativo a src/app/ -> idade em dias desde o
        ultimo commit que tocou aquele arquivo}`, construido com **uma
        unica** chamada de `git log` para todo o historico - ver nota de
        performance no docstring do modulo. O git lista commits do mais
        recente para o mais antigo, entao a primeira vez que um caminho
        aparece num bloco e o commit mais recente que o tocou."""
        output = _run_git(
            ["log", "--pretty=format:%x00%ct", "--name-only", "--", _APP_PATHSPEC]
        )
        now = datetime.now(UTC).timestamp()
        ages: dict[str, int] = {}
        for block in output.split("\x00"):
            block = block.strip("\n")
            if not block:
                continue
            block_lines = block.splitlines()
            epoch_line, paths = block_lines[0], block_lines[1:]
            if not epoch_line.strip().isdigit():
                continue
            commit_epoch = int(epoch_line.strip())
            for raw_path in paths:
                raw_path = raw_path.strip()
                if not raw_path.startswith(_APP_PATHSPEC):
                    continue
                relative = raw_path[len(_APP_PATHSPEC):]
                if relative not in ages:
                    ages[relative] = max(0, int((now - commit_epoch) // 86400))
        return ages

    def file_age_days(self, relative_path: str) -> int | None:
        """Idade em dias desde o ultimo commit que tocou `relative_path`
        (relativo a `src/app/` - mesmo formato que
        `CodeReviewService.review_repository()` usa em
        `per_file[i]["file"]`). Retorna `None` quando o arquivo nunca
        apareceu no historico rastreado pelo git (ex.: arquivo so em
        disco, nunca commitado) - nunca finge uma idade que nao foi
        medida de fato. Conveniencia para uso isolado/teste - internamente
        `debt_items()` constroi o mapa uma unica vez, nao chama isto por
        achado."""
        return self._file_age_days_map().get(relative_path)

    def debt_items(self) -> list[dict[str, Any]]:
        """Achados informativos de `CodeReviewService` (nunca os
        bloqueantes - esses ja tem tratamento proprio na Missao 56),
        enriquecidos com idade real (por arquivo) e pontuacao de
        prioridade."""
        report = self.code_review.review_repository()
        age_map = self._file_age_days_map()
        items: list[dict[str, Any]] = []
        for file_report in report["per_file"]:
            age_days = age_map.get(file_report["file"])
            age_known = age_days is not None
            known_age = age_days if age_known else 0
            for finding in file_report["findings"]:
                if finding["rule"] not in _DEBT_RULES:
                    continue
                weight = _RULE_WEIGHT[finding["rule"]]
                items.append(
                    {
                        "file": file_report["file"],
                        "line": finding["line"],
                        "rule": finding["rule"],
                        "detail": finding["detail"],
                        "age_days": known_age,
                        "age_known": age_known,
                        "priority_score": weight * (known_age + 1),
                    }
                )
        return items

    @staticmethod
    def prioritized_backlog(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Mesma lista de `items`, ordenada por `priority_score`
        descendente - responde "qual item resolver primeiro", nao so "o
        que existe"."""
        return sorted(items, key=lambda item: item["priority_score"], reverse=True)

    @staticmethod
    def hotspots(items: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
        """Arquivos com mais divida acumulada (por pontuacao total, nao
        so contagem), ordenados descendente - identifica onde concentrar
        esforco de limpeza primeiro."""
        counts: dict[str, int] = {}
        score_totals: dict[str, int] = {}
        for item in items:
            counts[item["file"]] = counts.get(item["file"], 0) + 1
            score_totals[item["file"]] = score_totals.get(item["file"], 0) + item["priority_score"]
        ranked_files = sorted(counts, key=lambda file: score_totals[file], reverse=True)
        return [
            {
                "file": file,
                "debt_item_count": counts[file],
                "total_score": score_totals[file],
            }
            for file in ranked_files[:top_n]
        ]

    @staticmethod
    def summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        items_by_rule: dict[str, int] = {}
        for item in items:
            items_by_rule[item["rule"]] = items_by_rule.get(item["rule"], 0) + 1
        return {
            "total_debt_items": len(items),
            "items_by_rule": dict(sorted(items_by_rule.items())),
            "files_with_debt": len({item["file"] for item in items}),
            "total_priority_score": sum(item["priority_score"] for item in items),
            "oldest_item_age_days": max((item["age_days"] for item in items), default=0),
            "items_with_unknown_age": sum(1 for item in items if not item["age_known"]),
        }

    def debt_report(self) -> dict[str, Any]:
        items = self.debt_items()
        return {
            "generated_at": datetime.now(UTC),
            "summary": self.summary(items),
            "hotspots": self.hotspots(items),
            "backlog": self.prioritized_backlog(items),
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.debt_report()
        summary = report["summary"]

        lines: list[str] = ["# Gestor Automatico de Divida Tecnica", ""]
        lines.append(f"- Itens de divida detectados: {summary['total_debt_items']}")
        lines.append(f"- Arquivos com divida: {summary['files_with_debt']}")
        lines.append(f"- Pontuacao total de prioridade: {summary['total_priority_score']}")
        lines.append(
            "- Arquivo mais antigo sem ser tocado (entre os com idade conhecida): "
            f"{summary['oldest_item_age_days']} dia(s)"
        )
        if summary["items_with_unknown_age"]:
            lines.append(
                "- Itens com idade desconhecida (arquivo fora do historico do git): "
                f"{summary['items_with_unknown_age']}"
            )
        lines.append("- Itens por regra:")
        for rule, count in summary["items_by_rule"].items():
            lines.append(f"  - {rule}: {count}")

        if report["hotspots"]:
            lines.append("")
            lines.append("## Hotspots (arquivos com mais divida acumulada)")
            for hotspot in report["hotspots"]:
                lines.append(
                    f"- {hotspot['file']}: {hotspot['debt_item_count']} item(ns), "
                    f"pontuacao {hotspot['total_score']}"
                )

        if report["backlog"]:
            lines.append("")
            lines.append("## Backlog priorizado (top 10)")
            for item in report["backlog"][:10]:
                age_note = f"{item['age_days']}d" if item["age_known"] else "idade desconhecida"
                lines.append(
                    f"- [{item['rule']}] {item['file']}:{item['line']} "
                    f"(pontuacao {item['priority_score']}, {age_note}) - {item['detail']}"
                )

        return "\n".join(lines)
