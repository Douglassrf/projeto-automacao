"""Domínio: FFmpeg Production Layer (Missão 83)."""

from pydantic import BaseModel


class FfmpegProductionConfig(BaseModel):
    ffmpeg_require_binary: bool = False
    ffmpeg_fallback_when_absent: bool = True
