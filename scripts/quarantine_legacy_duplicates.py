"""Missao G04 - Quarentena de duplicados e arquivos legados.

NUNCA apaga nada. Move (preserva 100% do conteudo) arquivos de backup
(`*.bak`, `*_backup`, `*_original_backup.py`) e pastas duplicadas
(nome contendo "Copia") encontrados no codigo-fonte do projeto para
`archived_legacy/`, preservando o caminho relativo original dentro
dessa pasta. Gera `legacy_manifest.json` com o inventario completo
(caminho original, caminho novo, tamanho, sha256, motivo) para que
nada se perca e tudo seja rastreavel.

Uso:
    python scripts/quarantine_legacy_duplicates.py [--dry-run]

--dry-run apenas mostra o que seria movido, sem mover nada.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = PROJECT_ROOT / "archived_legacy"
MANIFEST_PATH = PROJECT_ROOT / "legacy_manifest.json"

# Diretorios nunca varridos (irrelevantes para deteccao de duplicados de
# codigo-fonte, ou ja tratados por outras missoes).
PRUNE_DIR_NAMES = {
    ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".pytest_tmp",
    ".git", "_backups", "archived_legacy", "data", "node_modules", "logs",
}

# Scripts ativos cujo NOME contem "backup" por causa da FUNCAO que exercem
# (ex.: o proprio script que cria backups), e que portanto NAO sao
# duplicados legados. Excluidos explicitamente, com motivo documentado.
EXPLICIT_EXCLUDE_RELATIVE_PATHS = {
    "scripts/create_immutable_backup.py": (
        "Script ativo da missao G01R que CRIA backups imutaveis do projeto; "
        "o nome contem 'backup' pela funcao que exerce, nao e um duplicado "
        "de outro arquivo."
    ),
}

COPIA_DIR_SUBSTRING = "Copia"  # pasta duplicada em portugues (case-sensitive,
                                 # nao bate com "Copy"/"Copies" em ingles).


def is_backup_suffixed_extension(ext_no_dot: str) -> bool:
    """True para extensoes finais como 'bak', 'missao08_backup',
    'brain_backup', 'facebook_miner_backup', 'fase5_backup',
    'missao24B_backup', 'missao15_master_memory_backup', etc."""
    low = ext_no_dot.lower()
    if low == "bak":
        return True
    if low.endswith("_backup"):
        return True
    return False


def classify_file(path: Path) -> str | None:
    """Retorna o motivo da quarentena, ou None se o arquivo deve ficar."""
    rel = path.relative_to(PROJECT_ROOT).as_posix()
    if rel in EXPLICIT_EXCLUDE_RELATIVE_PATHS:
        return None

    name = path.name
    if "." not in name:
        return None
    stem, _, ext_no_dot = name.rpartition(".")

    # Caso 1: extensao final e o proprio marcador de backup
    # (ex.: "safe_router.py.missao08_backup", "meta_operator.py.bak")
    if is_backup_suffixed_extension(ext_no_dot):
        return f"extensao_final_de_backup(.{ext_no_dot})"

    # Caso 2: extensao normal (.py) mas o NOME (stem) termina em "_backup"
    # (ex.: "main_original_backup.py", "router_original_backup.py")
    if ext_no_dot.lower() == "py" and stem.endswith("_backup"):
        return "nome_de_arquivo_termina_em_backup"

    return None


def sha256_of_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def count_dir(path: Path) -> tuple[int, int]:
    files = 0
    total_bytes = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                files += 1
                total_bytes += p.stat().st_size
            except OSError:
                pass
    return files, total_bytes


def find_targets() -> tuple[list[Path], list[Path]]:
    """Retorna (arquivos_para_mover, pastas_para_mover)."""
    file_targets: list[Path] = []
    dir_targets: list[Path] = []
    handled_dir_prefixes: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        current = Path(dirpath)

        # Nao descer em pastas ja marcadas para mover por inteiro
        if any(str(current).startswith(str(p)) for p in handled_dir_prefixes):
            dirnames[:] = []
            continue

        # Prune padrao
        keep_dirnames = []
        for d in dirnames:
            if d in PRUNE_DIR_NAMES:
                continue
            if COPIA_DIR_SUBSTRING in d:
                full = current / d
                dir_targets.append(full)
                handled_dir_prefixes.append(full)
                continue
            keep_dirnames.append(d)
        dirnames[:] = keep_dirnames

        for fn in filenames:
            full = current / fn
            reason = classify_file(full)
            if reason:
                file_targets.append(full)

    return file_targets, dir_targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Apenas lista, nao move nada.")
    args = parser.parse_args()

    file_targets, dir_targets = find_targets()

    entries = []
    moved_files = 0
    moved_dirs = 0
    moved_bytes = 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    for path in sorted(dir_targets):
        rel = path.relative_to(PROJECT_ROOT)
        dest = ARCHIVE_DIR / rel
        file_count, total_bytes = count_dir(path)
        entry = {
            "type": "directory",
            "original_path": str(rel.as_posix()),
            "new_path": str((Path("archived_legacy") / rel).as_posix()),
            "reason": f"nome_de_pasta_contem('{COPIA_DIR_SUBSTRING}')",
            "file_count": file_count,
            "total_bytes": total_bytes,
            "moved": False,
        }
        if not args.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
            entry["moved"] = True
            moved_dirs += 1
            moved_bytes += total_bytes
        entries.append(entry)

    for path in sorted(file_targets):
        rel = path.relative_to(PROJECT_ROOT)
        dest = ARCHIVE_DIR / rel
        reason = classify_file(path)
        try:
            size_bytes = path.stat().st_size
            digest = sha256_of_file(path)
        except OSError as exc:
            size_bytes = -1
            digest = f"ERRO:{exc}"
        entry = {
            "type": "file",
            "original_path": str(rel.as_posix()),
            "new_path": str((Path("archived_legacy") / rel).as_posix()),
            "reason": reason,
            "size_bytes": size_bytes,
            "sha256": digest,
            "moved": False,
        }
        if not args.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
            entry["moved"] = True
            moved_files += 1
            moved_bytes += max(size_bytes, 0)
        entries.append(entry)

    manifest = {
        "mission": "G04",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "dry_run": args.dry_run,
        "archive_dir": str(ARCHIVE_DIR.relative_to(PROJECT_ROOT).as_posix()),
        "explicit_excluded_paths": EXPLICIT_EXCLUDE_RELATIVE_PATHS,
        "summary": {
            "directories_found": len(dir_targets),
            "files_found": len(file_targets),
            "directories_moved": moved_dirs,
            "files_moved": moved_files,
            "total_bytes_moved": moved_bytes,
        },
        "entries": entries,
        "policy": "Nunca apaga. Apenas move (preserva 100% do conteudo) para archived_legacy/.",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Modo: {'DRY-RUN (nada foi movido)' if args.dry_run else 'EXECUCAO REAL'}")
    print(f"Pastas encontradas: {len(dir_targets)} | movidas: {moved_dirs}")
    print(f"Arquivos encontrados: {len(file_targets)} | movidos: {moved_files}")
    print(f"Total de bytes movidos: {moved_bytes}")
    print(f"Manifesto: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
