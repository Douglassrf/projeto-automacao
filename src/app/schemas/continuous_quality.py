from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ContinuousQualityResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    enforce_standards: bool
    test_coverage: dict[str, Any]
    technical_debt: dict[str, Any]
    code_pattern_checks: list[dict[str, str]]
    release_report: dict[str, Any]
    config_validation_issues: list[str]
