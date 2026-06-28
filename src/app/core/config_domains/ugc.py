"""Domínio: processamento de UGC (User Generated Content)."""

from pydantic import BaseModel


class UGCConfig(BaseModel):
    ugc_output_dir: str = "/data/ugc"
    ugc_max_bytes: int = 50 * 1024 * 1024
    ugc_image_target_width: int = 1080
    ugc_video_target_width: int = 720
    ugc_video_crf: int = 28
