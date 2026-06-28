"""Domínio: integrações de nuvem experimentais/exploratórias."""

from pydantic import BaseModel


class CloudExperimentalConfig(BaseModel):
    google_cloud_run_project: str | None = None
    aws_lambda_region: str | None = None
    colab_notebook_url: str | None = None
    comfyui_endpoint: str | None = None
