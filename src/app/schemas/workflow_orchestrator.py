from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WorkflowOrchestratorResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    track_progress: bool
    allow_parallel: bool
    workflow_steps: list[dict[str, Any]]
    progress: dict[str, Any]
    queue_health: dict[str, Any]
    config_validation_issues: list[str]
