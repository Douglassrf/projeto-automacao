from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReleaseCandidateResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    mission_number: int
    verdict: str
    ready: bool
    blocking_issues: list[str]
    blocking_issue_count: int
    evidence: dict[str, Any]
