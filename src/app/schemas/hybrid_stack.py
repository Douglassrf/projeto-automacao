from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from typing import Literal


class HybridStackRequest(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=120)
    goal: str = Field("Gerar campanha multimídia com custo zero", max_length=240)
    has_gpu: bool = False
    prefer_free_tier: bool = True
    use_colab: bool = True
    use_github_actions: bool = True
    deploy_target: Literal["cloud_run", "aws_lambda", "vercel", "netlify", "local_only"] = "vercel"
    llm_provider: Literal["rag_gemini", "ollama_cpu", "openai", "local_template"] = "ollama_cpu"
    media_provider: Literal["colab_comfyui", "huggingface_spaces", "leonardo_manual", "prompt_only"] = "colab_comfyui"
    repository_url: HttpUrl | None = None


class HybridStackStep(BaseModel):
    order: int
    layer: str
    action: str
    provider: str
    mode: str
    output: str | None = None
    notes: list[str] = Field(default_factory=list)


class HybridStackResponse(BaseModel):
    product_name: str
    generated_at: datetime
    architecture_mode: str
    estimated_fixed_cost: str
    output_dir: str
    plan_file: str
    github_actions_file: str
    cloud_run_dockerfile: str
    rag_manifest_file: str
    steps: list[HybridStackStep]
    warnings: list[str] = Field(default_factory=list)
