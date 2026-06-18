from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class VideoRenderRequest(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=180)
    model: str = Field("V1", pattern="^(V1|V2|V3|V4|V5|V6)$")
    hook: str = Field(..., min_length=3, max_length=220)
    script: str = Field(..., min_length=10, max_length=4000)
    cta: str = Field("Acesse agora", max_length=180)
    language: str = Field("auto", max_length=80)
    aspect_ratio: str = Field("9:16", pattern="^(9:16|1:1|16:9)$")
    voice_provider: str = Field("auto", pattern="^(auto|fallback|elevenlabs|openai)$")
    scene_provider: str = Field("ffmpeg_local", pattern="^(ffmpeg_local|huggingface_svd)$")
    duration_seconds: int | None = Field(None, ge=1, le=90)


class VideoRenderResponse(BaseModel):
    product_name: str
    model: str
    generated_at: datetime
    provider: str
    output_folder: str
    script_file: str
    audio_file: str
    video_file: str
    final_mp4: str
    duration_seconds: float
    status: str
    warnings: list[str] = Field(default_factory=list)
