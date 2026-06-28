from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ArchitectureEvolutionResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    app_version: str | None
    include_recommendations: bool
    version_milestones: list[dict[str, str]]
    current_vs_previous: dict[str, Any]
    complexity_indicators: dict[str, Any]
    refactoring_areas: list[str]
    technical_recommendations: list[str]
    config_validation_issues: list[str]
