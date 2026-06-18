from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class UGCProcessResponse(BaseModel):
    status: str
    asset_id: str
    media_type: str
    original_filename: str
    safe_original_filename: str
    generated_at: datetime
    raw_path: str
    processed_path: str
    input_size_bytes: int
    output_size_bytes: int
    savings_percent: float
    target_preset: str
    ffmpeg_command: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
