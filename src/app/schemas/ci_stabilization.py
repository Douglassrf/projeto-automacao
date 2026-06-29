from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CiStabilizationResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    require_green_pipeline: bool
    verdict: str
    pipeline_ready: bool
    blocking_issues: list[str]
    blocking_issue_count: int
    workflow_files: list[str]
    flaky_tests_tracked: list[str]
    ffmpeg_windows_skip_enabled: bool
    evidence: dict[str, Any]
