from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from typing import Literal

from app.schemas.war_kit import MinedAdPattern, ProductDNAInput


class OrchestrationRequest(BaseModel):
    product: ProductDNAInput
    mined_ads: list[MinedAdPattern] = Field(default_factory=list, max_length=50)
    workflow_name: str = Field("AdIntelligence Free Stack Pipeline", max_length=120)
    run_mode: Literal["plan_only", "dry_run", "execute_local"] = "dry_run"
    include_site: bool = True
    include_video: bool = True
    include_images: bool = True
    include_deploy_payload: bool = True
    n8n_webhook_url: HttpUrl | None = None
    image_provider: Literal["prompt_only", "huggingface_sd"] = "prompt_only"
    voice_provider: Literal["fallback", "elevenlabs", "openai", "auto"] = "auto"
    video_provider: Literal["ffmpeg_local", "huggingface_svd"] = "ffmpeg_local"
    deploy_provider: Literal["local", "github_vercel", "vercel", "netlify"] = "local"


class OrchestrationStep(BaseModel):
    order: int
    name: str
    tool: str
    status: str
    output: str | None = None
    notes: list[str] = Field(default_factory=list)


class OrchestrationResponse(BaseModel):
    product_name: str
    generated_at: datetime
    run_mode: str
    output_dir: str
    pipeline_json: str
    bash_runner: str
    n8n_workflow: str
    steps: list[OrchestrationStep]
    war_kit_folder: str | None = None
    site_preview: str | None = None
    video_mp4: str | None = None
    deploy_payload: str | None = None
    warnings: list[str] = Field(default_factory=list)
