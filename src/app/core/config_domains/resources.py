"""Domínio: gerenciamento de recursos/jobs (Missão 45)."""

from pydantic import BaseModel


class ResourcesConfig(BaseModel):
    resource_job_retention_days: int = 30
