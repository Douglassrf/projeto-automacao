"""Domínio: armazenamento de arquivos gerados."""

from pydantic import BaseModel


class StorageConfig(BaseModel):
    storage_provider: str = "local"
    s3_bucket: str | None = None
    drive_folder_id: str | None = None
