from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from typing import Literal


class ServerlessRenderRequest(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=120)
    asset_type: Literal["image", "video", "site_preview"] = "image"
    prompt: str = Field(..., min_length=10, max_length=4000)
    provider: Literal["aws_lambda", "google_cloud_functions", "cloud_run_job", "huggingface_space", "dry_run"] = "dry_run"
    target_runtime: Literal["python311", "python312", "node20"] = "python311"
    storage_target: Literal["supabase_storage", "s3", "cloudinary", "local"] = "local"
    callback_url: HttpUrl | None = None
    max_cost_usd: float = Field(0.0, ge=0)
    dry_run: bool = True


class ServerlessRenderJobResponse(BaseModel):
    status: Literal["queued", "dry_run", "error"] = "dry_run"
    job_id: str
    product_name: str
    asset_type: str
    provider: str
    generated_at: datetime
    queue_payload_file: str
    aws_lambda_payload_file: str
    google_function_payload_file: str
    github_actions_file: str
    estimated_fixed_cost: str
    next_step: str
    guardrails: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
