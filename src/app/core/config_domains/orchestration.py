"""Domínio: orquestração de execuções e webhooks (n8n)."""

from pydantic import BaseModel


class OrchestrationConfig(BaseModel):
    orchestration_output_dir: str = "/data/orchestration_runs"
    n8n_base_url: str | None = None
    n8n_webhook_secret: str | None = None
