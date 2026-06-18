from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from app.core.config import get_settings


@dataclass
class StorageUploadResult:
    provider: str
    status: str
    url: str | None = None
    message: str = ""


class CampaignKitStorageProvider:
    """Conector de armazenamento. Local é funcional; S3/Drive ficam como adaptadores seguros.

    A ferramenta não expõe credenciais no frontend. Quando S3/Drive forem configurados,
    este ponto é o encaixe para SDK oficial, mantendo o pipeline intacto.
    """

    def upload_folder(self, folder: Path) -> StorageUploadResult:
        settings = get_settings()
        if settings.storage_provider == "local":
            return StorageUploadResult(provider="local", status="stored_local", url=str(folder), message="Kit salvo na pasta local.")
        if settings.storage_provider == "s3":
            if not settings.s3_bucket:
                return StorageUploadResult(provider="s3", status="skipped", message="S3_BUCKET não configurado.")
            return StorageUploadResult(provider="s3", status="adapter_ready", message="Adaptador S3 pronto; instalar boto3 e credenciais AWS para upload real.")
        if settings.storage_provider == "drive":
            if not settings.drive_folder_id:
                return StorageUploadResult(provider="drive", status="skipped", message="DRIVE_FOLDER_ID não configurado.")
            return StorageUploadResult(provider="drive", status="adapter_ready", message="Adaptador Drive pronto; conectar OAuth/Service Account para upload real.")
        return StorageUploadResult(provider=settings.storage_provider, status="unsupported", message="Provider não suportado.")
