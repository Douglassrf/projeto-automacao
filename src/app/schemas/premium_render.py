from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class PremiumRenderRequest(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=160)
    asset_type: Literal["image", "video"] = "image"
    prompt: str = Field(..., min_length=10, max_length=4000)
    source_asset_path: str | None = Field(None, max_length=600)
    provider: Literal["dry_run", "flux", "sdxl", "runway", "kling", "local_ffmpeg"] = "dry_run"
    upscale: bool = True
    color_grade: Literal["none", "warm_contrast", "cinematic", "social_pop"] = "warm_contrast"
    dispatch_mode: Literal["local", "celery", "queue_payload"] = "local"
    dry_run: bool = True


class PremiumRenderResponse(BaseModel):
    status: Literal["created", "queued", "dry_run"]
    render_id: str
    product_name: str
    asset_type: str
    provider: str
    dispatch_mode: str
    generated_at: datetime
    output_folder: str
    base_asset_file: str
    upscaled_file: str | None = None
    color_graded_file: str | None = None
    final_file: str
    worker_payload_file: str
    celery_task_id: str | None = None
    observability_event: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class WorkerBlueprintResponse(BaseModel):
    queue: str
    celery_enabled: bool
    broker_url_masked: str
    result_backend_masked: str
    start_command: str
    fallback_queue: str
    observability: dict
    notes: list[str] = Field(default_factory=list)
