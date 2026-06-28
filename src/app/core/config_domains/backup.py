"""Domínio: backup local do banco de dados (Codex — Missões 31-40)."""

from pydantic import BaseModel


class BackupConfig(BaseModel):
    backup_dir: str = "./backups"
    backup_retention: int = 14
