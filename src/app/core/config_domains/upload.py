"""Domínio: upload de arquivos."""

from pydantic import BaseModel


class UploadConfig(BaseModel):
    upload_max_bytes: int = 5 * 1024 * 1024
    upload_dir: str = "/data/uploads"
