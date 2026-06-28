"""Domínio: renderização serverless."""

from pydantic import BaseModel


class ServerlessRenderConfig(BaseModel):
    serverless_render_enabled: bool = True
    serverless_render_provider: str = "dry_run"
    serverless_render_max_cost_usd: float = 0.0
    aws_lambda_render_function_name: str | None = None
    google_cloud_function_render_url: str | None = None
    render_callback_url: str | None = None
