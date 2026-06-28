"""Domínio: pipeline de renderização de vídeo."""

from pydantic import BaseModel


class VideoConfig(BaseModel):
    video_provider: str = "ffmpeg_local"
    war_kit_execute_video_render: bool = False
