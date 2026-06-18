"""Missao G02 - Auditoria de segredos antes do Git.

Varre o projeto procurando:
  - arquivos .env reais (exceto .env.example);
  - arquivos *.db / *.sqlite (bancos locais);
  - segredos provavelmente reais "hardcoded" em qualquer outro arquivo de
    texto: uma atribuicao onde a PROPRIA CHAVE (nome da variavel/campo) e
    sensivel e o VALOR e um literal que nao parece placeholder/teste.

Gera secrets_audit_report.json na raiz do projeto.

Saida (exit code):
  0 = liberado para avancar (G03).
  1 = bloqueado (segredo real hardcoded encontrado em arquivo que iria
      para o Git).

Importante: o relatorio gerado NUNCA contem o valor real do segredo --
apenas caminho, linha, nome da chave/keyword e classificacao.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".pytest_tmp",
    ".git",
    "_backups",
    "archived_legacy",
    "node_modules",
}

BINARY_EXTENSIONS = {
    ".zip", ".exe", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
    ".sha256",
}

SENSITIVE_KEYWORDS = [
    "JWT_SECRET",
    "SECRET_KEY",
    "META_ACCESS_TOKEN",
    "FACEBOOK_ACCESS_TOKEN",
    "STRIPE",
    "MERCADO_PAGO",
    "DATABASE_URL",
    "PASSWORD",
    "TOKEN",
    "PRIVATE_KEY",
    "CREDENTIALS",
    "CLIENT_SECRET",
]

# Pedacos (case-insensitive) que, se presentes no VALOR atribuido, indicam
# placeholder / valor de exemplo / valor de teste / valor de dev local --
# e portanto NAO um segredo real que precise bloquear o avanco.
PLACEHOLDER_HINTS = [
    "your_", "changeme", "change-me", "change_me", "example", "placeholder",
    "xxx", "sample", "dummy", "fake", "test", "rotated", "<", ">", "{{",
    "os.getenv", "os.environ", "getenv(", "environ[", "environ.get",
    "process.env", "replace_me", "todo", "fixme", "********", "redacted",
    "mock", "local_dev_only", "local-key", "n/a", "sqlite://", "bearer",
    "''", '""',
]

# Duas formas de atribuicao cobertas:
#  1) "chave = 'valor'" ou dict-style "chave": "valor" (sem tipo no meio) --
#     cobre `settings.meta_access_token = "..."` e `"jwt_secret": "..."`.
#  2) atribuicao com type hint do Python: "chave: Tipo = 'valor'" -- cobre
#     campos de Pydantic/dataclass como `jwt_secret_key: str = "..."`.
ASSIGNMENT_RE_SIMPLE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_\.]*)\s*[:=]\s*[\"']{1}(?P<value>[^\"']{6,})[\"']{1}"
)
ASSIGNMENT_RE_TYPED = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*[^=\n]{1,60}?=\s*[\"']{1}(?P<value>[^\"']{6,})[\"']{1}"
)

def iter_assignments(line: str):
    for pattern in (ASSIGNMENT_RE_SIMPLE, ASSIGNMENT_RE_TYPED):
        for m in pattern.finditer(line):
            yield m.group("key"), m.group("value")


def is_real_env_file(filename: str) -> bool:
    if filename == ".env":
        return True
    if filename.startswith(".env.") and filename != ".env.example":
        return True
    if filename.endswith(".env") and filename != ".env.example":
        return True
    return False


def is_db_file(filename: str) -> bool:
    return filename.endswith((".db", ".sqlite", ".sqlite3"))


def looks_like_placeholder(value: str) -> bool:
    low = value.lower()
    return any(hint in low for hint in PLACEHOLDER_HINTS)


def key_is_sensitive(key: str) -> list[str]:
    key_upper = key.upper()
    return [k for k in SENSITIVE_KEYWORDS if k in key_upper]


def scan_text_file(path: Path, rel_path: str):
    """Retorna lista de achados (dict) para um arquivo de texto comum.

    So classifica HIGH quando a propria CHAVE da atribuicao e sensivel
    (nao basta a keyword aparecer em outro lugar da linha).
    """
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        upper_line = line.upper()
        line_has_keyword = any(k in upper_line for k in SENSITIVE_KEYWORDS)
        if not line_has_keyword:
            continue

        high_matches = []
        for key, value in iter_assignments(line):
            matched_keywords = key_is_sensitive(key)
            if not matched_keywords:
                continue
            if not looks_like_placeholder(value):
                high_matches.append(matched_keywords)

        if high_matches:
            all_keywords = sorted({k for group in high_matches for k in group})
            findings.append(
                {
                    "file": rel_path,
                    "line": lineno,
                    "keywords": all_keywords,
                    "severity": "HIGH_possible_hardcoded_secret",
                }
            )
        else:
            matched_keywords = [k for k in SENSITIVE_KEYWORDS if k in upper_line]
            findings.append(
                {
                    "file": rel_path,
                    "line": lineno,
                    "keywords": matched_keywords,
                    "severity": "INFO_reference_or_placeholder",
                }
            )
    return findings


def main() -> int:
    real_env_files = []
    db_files = []
    high_severity = []
    info_findings = []

    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for filename in filenames:
            full_path = Path(dirpath) / filename
            rel_path = str(full_path.relative_to(PROJECT_ROOT))

            if is_real_env_file(filename):
                try:
                    size = full_path.stat().st_size
                except OSError:
                    size = None
                real_env_files.append({"path": rel_path, "size_bytes": size, "non_empty": bool(size)})
                continue

            if is_db_file(filename):
                try:
                    size = full_path.stat().st_size
                except OSError:
                    size = None
                db_files.append({"path": rel_path, "size_bytes": size})
                continue

            if full_path.suffix.lower() in BINARY_EXTENSIONS:
                continue

            findings = scan_text_file(full_path, rel_path)
            for f in findings:
                if f["severity"].startswith("HIGH"):
                    high_severity.append(f)
                else:
                    info_findings.append(f)

    status = "BLOQUEADO" if high_severity else "LIBERADO"

    report = {
        "mission": "G02",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "status": status,
        "real_env_files_found": real_env_files,
        "db_files_found": db_files,
        "high_severity_findings": high_severity,
        "high_severity_count": len(high_severity),
        "info_findings_count": len(info_findings),
        "info_findings_sample": info_findings[:50],
        "criterio": (
            "BLOQUEADO se houver uma atribuicao onde a CHAVE e sensivel "
            "(ex: jwt_secret_key=, default_admin_password=, meta_access_token=) "
            "e o VALOR literal nao parece placeholder/teste/exemplo. "
            ".env real e *.db sao esperados localmente e devem ser cobertos "
            "pelo .gitignore (missao G03), nao bloqueiam aqui."
        ),
    }

    report_path = PROJECT_ROOT / "secrets_audit_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Status: {status}")
    print(f"Arquivos .env reais encontrados: {len(real_env_files)}")
    print(f"Arquivos de banco encontrados: {len(db_files)}")
    print(f"Achados HIGH (possivel segredo hardcoded): {len(high_severity)}")
    print(f"Achados INFO (referencia/placeholder): {len(info_findings)}")
    print(f"Relatorio: {report_path}")
    return 1 if high_severity else 0


if __name__ == "__main__":
    sys.exit(main())
