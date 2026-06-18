"""Missao G01R - Backup imutavel do Projeto Automacao (refeito).

Cria um ZIP completo do projeto (excluindo apenas lixo regeneravel como
__pycache__/.pytest_cache, a propria pasta de backups, e binarios de
terceiros regeneraveis) e salva DENTRO da pasta do projeto, em
`_backups/` -- pasta persistente e conectada.

A tentativa original (G01) salvava FORA da pasta conectada (sibling da
raiz do projeto) e por isso o backup se perdia ao fim da sessao; esta
versao corrige isso.

Gera tambem um hash SHA256 do ZIP e um backup_manifest.json com os
metadados completos (nome, caminho absoluto, tamanho, SHA256, data/hora,
total de arquivos, total de pastas, arquivos excluidos e confirmacao de
existencia do ZIP).

Uso:
    python scripts/create_immutable_backup.py [--output-dir CAMINHO]

Se --output-dir nao for informado, usa <raiz_do_projeto>/_backups/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".pytest_tmp",
    ".git",
    "_backups",
}

# Binarios de terceiros, regeneraveis (re-baixaveis), que ja sao ignorados
# pelo .gitignore do projeto. Excluidos aqui apenas por motivo de
# performance de I/O sobre a pasta conectada (rede/FUSE) -- nao sao
# codigo nem dado unico do projeto. Registrados no manifesto para
# transparencia total.
EXCLUDE_FILE_NAMES = {
    "ffmpeg.exe",
}


def iter_project_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for filename in filenames:
            if filename in EXCLUDE_FILE_NAMES:
                continue
            yield Path(dirpath) / filename


def iter_excluded_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for filename in filenames:
            if filename in EXCLUDE_FILE_NAMES:
                yield Path(dirpath) / filename


def count_dirs(root: Path) -> int:
    total = 0
    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        total += len(dirnames)
    return total


def sha256_of_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def default_output_dir() -> Path:
    return PROJECT_ROOT / "_backups"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Pasta onde o backup sera salvo (padrao: _backups dentro do projeto).",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_name = f"projeto_automacao_backup_{timestamp}.zip"
    zip_path = output_dir / zip_name

    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        for file_path in iter_project_files(PROJECT_ROOT):
            arcname = file_path.relative_to(PROJECT_ROOT)
            try:
                zf.write(file_path, arcname=str(arcname))
                file_count += 1
                total_bytes += file_path.stat().st_size
            except (PermissionError, OSError) as exc:
                print(f"AVISO: nao foi possivel ler {file_path}: {exc}")

    dir_count = count_dirs(PROJECT_ROOT)
    zip_exists = zip_path.is_file()
    zip_size_bytes = zip_path.stat().st_size if zip_exists else 0

    excluded_files_info = []
    for excluded_path in iter_excluded_files(PROJECT_ROOT):
        try:
            excluded_files_info.append(
                {
                    "path": str(excluded_path.relative_to(PROJECT_ROOT)),
                    "size_bytes": excluded_path.stat().st_size,
                }
            )
        except OSError:
            pass

    zip_sha256 = sha256_of_file(zip_path)
    sha_path = output_dir / f"{zip_name}.sha256"
    sha_path.write_text(f"{zip_sha256}  {zip_name}\n", encoding="utf-8")

    manifest = {
        "mission": "G01R",
        "created_at_utc": timestamp,
        "project_root": str(PROJECT_ROOT),
        "backup_zip_name": zip_name,
        "backup_zip_path_absolute": str(zip_path.resolve()),
        "backup_zip_size_bytes": zip_size_bytes,
        "backup_zip_exists": zip_exists,
        "backup_zip_sha256": zip_sha256,
        "sha256_file_path_absolute": str(sha_path.resolve()),
        "source_files_count": file_count,
        "source_total_bytes": total_bytes,
        "source_dirs_count": dir_count,
        "excluded_dir_names": sorted(EXCLUDE_DIR_NAMES),
        "excluded_file_names": sorted(EXCLUDE_FILE_NAMES),
        "excluded_files_detail": excluded_files_info,
        "excluded_files_reason": (
            "Binarios de terceiros regeneraveis (ja ignorados pelo .gitignore do "
            "projeto), excluidos apenas por performance de I/O sobre a pasta "
            "conectada via rede/FUSE. Nao sao codigo nem dado unico do projeto."
        ),
        "note": (
            "Backup completo de desastre (inclui .env e banco local). Salvo "
            "dentro da pasta conectada do projeto, nao em ambiente temporario. "
            "Nao deve ser usado como base para o que entra no Git - isso e "
            "definido pela missao G03."
        ),
    }
    manifest_path = output_dir / "backup_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Backup criado: {zip_path}")
    print(f"Existe: {zip_exists}")
    print(f"Arquivos incluidos: {file_count}")
    print(f"Pastas incluidas: {dir_count}")
    print(f"Tamanho do ZIP (bytes): {zip_size_bytes}")
    print(f"SHA256: {zip_sha256}")
    print(f"Manifesto: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
