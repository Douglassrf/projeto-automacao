from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ZeroCostStackRequest(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=120)
    campaign_goal: str = Field("Gerar campanha completa sem GPU própria", max_length=260)
    theme: str = Field("Produto digital de alta conversão", max_length=240)
    llm_provider: Literal["gemini_free", "ollama_cpu", "local_template"] = "gemini_free"
    render_provider: Literal["google_colab_comfyui", "huggingface_spaces", "leonardo_manual", "prompt_only"] = "google_colab_comfyui"
    orchestrator: Literal["n8n_cloud_trial", "n8n_self_hosted", "bash_only"] = "n8n_self_hosted"
    deploy_provider: Literal["github_actions_vercel", "github_actions_netlify", "cloud_run", "local_only"] = "github_actions_vercel"
    repository_url: HttpUrl | None = None
    dry_run: bool = True


class ZeroCostStackArtifact(BaseModel):
    name: str
    path: str
    purpose: str


class ZeroCostStackResponse(BaseModel):
    product_name: str
    generated_at: datetime
    mode: str
    output_dir: str
    fixed_cost_strategy: str
    execution_order: list[str]
    artifacts: list[ZeroCostStackArtifact]
    guardrails: list[str]
    warnings: list[str] = Field(default_factory=list)
