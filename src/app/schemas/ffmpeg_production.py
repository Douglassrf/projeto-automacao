from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FfmpegProductionResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    mission_number: int
    verdict: str
    ready: bool
    blocking_issues: list[str]
    blocking_issue_count: int
    ffmpeg_available: bool
    ffmpeg_path: str | None
    fallback_enabled: bool
    evidence: dict[str, Any]
