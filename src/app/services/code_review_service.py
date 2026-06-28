"""Missao 56 - AI Code Reviewer.

Contexto: a CLAUDE.md do projeto (regra 6) proibe usar APIs pagas, cloud ou
servicos externos sem Douglas pedir - isso inclui chamar uma API de LLM de
terceiros so para "revisar codigo com IA" literalmente. Por isso, o "AI"
desta missao e um motor de revisao automatica baseado em analise estatica
real (AST), no mesmo espirito heuristico, consistente e instantaneo que um
revisor humano senior aplicaria - sem custo, sem rede, sem dependencia
externa. Mesma decisao de design ja tomada (e documentada) nas Missoes
51-55 desta serie: nunca pagar por algo que pode ser feito lendo o proprio
codigo-fonte.

Eixos verificados, cada um por leitura de AST do codigo-fonte real (nunca
snapshot estatico - mesmo principio "continuo" da Missao 55):

Bloqueantes (contradizem a filosofia "falhar visivel, nunca silencioso" ja
repetida nas Missoes 46, 50 e 53 desta serie):
- bare_except: `except:` sem tipo - engole qualquer erro silenciosamente.
- mutable_default_argument: lista/dict/set como valor padrao de parametro -
  bug classico de estado compartilhado entre chamadas.
- wildcard_import: `from modulo import *` - esconde de onde cada nome vem.
- syntax_error: arquivo que nem chega a fazer parse - nunca escondido.

Informativos (nao bloqueiam o veredito `clean` - mesma filosofia de
`di_adoption` na Missao 55: sinal de acompanhamento, nao contrato rigido):
- missing_docstring: funcao/classe publica sem docstring.
- long_function: funcao com corpo maior que o limiar informativo (escopo de
  revisao dificil, candidata a quebra em partes menores).
- todo_marker: comentario com TODO/FIXME - rastreado, nunca escondido.

Escopo: `app/` inteiro, exceto `app/tests/` (testes legitimamente usam
padroes - asserts crus, fixtures, funcoes de teste longas e repetitivas -
que nao se aplicam a codigo de producao).

Garantia de leitura pura: nenhum metodo aqui escreve em disco ou no banco -
so le arquivos `.py` do proprio repositorio.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from app.core.config import project_root

_LONG_FUNCTION_LINE_THRESHOLD = 60
_EXCLUDED_DIR_NAMES = {"tests", "__pycache__"}


def _app_root() -> Path:
    return project_root() / "src" / "app"


class CodeReviewService:
    """Missao 56. Le-only. Nao recebe `db` no construtor: todos os eixos
    leem arquivos `.py` do proprio repositorio via AST, nunca o banco -
    mesmo motivo documentado em `ArchitectureAuditService` (Missao 55)."""

    def _scannable_files(self) -> list[Path]:
        app_root = _app_root()
        files: list[Path] = []
        for path in sorted(app_root.rglob("*.py")):
            if any(part in _EXCLUDED_DIR_NAMES for part in path.parts):
                continue
            files.append(path)
        return files

    def review_file(
        self,
        path: Path | None = None,
        source: str | None = None,
        *,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Revisa um unico arquivo. `source`/`label` existem para permitir
        teste unitario com codigo sintetico, sem precisar de um arquivo real
        em disco - mesmo padrao de `source: str | None` ja usado nos quatro
        eixos de `ArchitectureAuditService` (Missao 55)."""
        if source is None and path is None:
            raise ValueError("review_file requer `path` ou `source`")

        if source is not None:
            text = source
            name = label or "<source>"
        else:
            assert path is not None
            text = path.read_text(encoding="utf-8")
            name = label or str(path)

        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            finding = {
                "rule": "syntax_error",
                "severity": "blocking",
                "line": exc.lineno or 0,
                "detail": f"arquivo nao faz parse: {exc.msg}",
            }
            return {"file": name, "findings": [finding], "blocking_count": 1}

        findings: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append({
                    "rule": "bare_except",
                    "severity": "blocking",
                    "line": node.lineno,
                    "detail": "except: sem tipo - engole qualquer erro silenciosamente",
                })
            elif isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                findings.append({
                    "rule": "wildcard_import",
                    "severity": "blocking",
                    "line": node.lineno,
                    "detail": f"from {node.module or '?'} import * - esconde de onde cada nome vem",
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defaults = [d for d in (node.args.defaults + node.args.kw_defaults) if d is not None]
                if any(isinstance(d, (ast.List, ast.Dict, ast.Set)) for d in defaults):
                    findings.append({
                        "rule": "mutable_default_argument",
                        "severity": "blocking",
                        "line": node.lineno,
                        "detail": f"{node.name}() usa lista/dict/set como valor padrao - estado compartilhado entre chamadas",
                    })
                if not node.name.startswith("_") and ast.get_docstring(node) is None:
                    findings.append({
                        "rule": "missing_docstring",
                        "severity": "informative",
                        "line": node.lineno,
                        "detail": f"{node.name}() e publica e nao tem docstring",
                    })
                if node.end_lineno and (node.end_lineno - node.lineno) > _LONG_FUNCTION_LINE_THRESHOLD:
                    findings.append({
                        "rule": "long_function",
                        "severity": "informative",
                        "line": node.lineno,
                        "detail": (
                            f"{node.name}() tem {node.end_lineno - node.lineno} linhas "
                            f"(limiar informativo: {_LONG_FUNCTION_LINE_THRESHOLD})"
                        ),
                    })

        for line_number, line_text in enumerate(text.splitlines(), start=1):
            if "TODO" in line_text or "FIXME" in line_text:
                findings.append({
                    "rule": "todo_marker",
                    "severity": "informative",
                    "line": line_number,
                    "detail": line_text.strip()[:120],
                })

        blocking_count = sum(1 for finding in findings if finding["severity"] == "blocking")
        return {"file": name, "findings": findings, "blocking_count": blocking_count}

    def review_repository(self) -> dict[str, Any]:
        app_root = _app_root()
        files = self._scannable_files()
        per_file: list[dict[str, Any]] = []
        rule_counts: dict[str, int] = {}
        total_blocking = 0

        for path in files:
            result = self.review_file(path=path, label=str(path.relative_to(app_root)))
            if result["findings"]:
                per_file.append(result)
            for finding in result["findings"]:
                rule_counts[finding["rule"]] = rule_counts.get(finding["rule"], 0) + 1
            total_blocking += result["blocking_count"]

        return {
            "clean": total_blocking == 0,
            "total_files_scanned": len(files),
            "files_with_findings": len(per_file),
            "total_blocking_findings": total_blocking,
            "rule_counts": dict(sorted(rule_counts.items())),
            "per_file": per_file,
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.review_repository()
        verdict = (
            "REVISAO LIMPA (sem achado bloqueante)"
            if report["clean"]
            else "ACHADO BLOQUEANTE DETECTADO"
        )
        lines: list[str] = [f"# Revisao Automatica de Codigo - {verdict}", ""]
        lines.append(f"- Arquivos varridos: {report['total_files_scanned']}")
        lines.append(f"- Arquivos com algum achado: {report['files_with_findings']}")
        lines.append(f"- Achados bloqueantes: {report['total_blocking_findings']}")
        lines.append("- Achados por regra:")
        for rule, count in report["rule_counts"].items():
            lines.append(f"  - {rule}: {count}")

        if report["total_blocking_findings"]:
            lines.append("")
            lines.append("## Achados bloqueantes (detalhe)")
            for file_report in report["per_file"]:
                blocking = [f for f in file_report["findings"] if f["severity"] == "blocking"]
                if not blocking:
                    continue
                lines.append(f"### {file_report['file']}")
                for finding in blocking:
                    lines.append(f"- linha {finding['line']}: [{finding['rule']}] {finding['detail']}")

        return "\n".join(lines)
