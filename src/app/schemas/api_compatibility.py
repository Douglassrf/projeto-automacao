from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ApiCompatibilityResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    api_version: str
    enforce_deprecation_policy: bool
    routes_summary: dict[str, Any]
    compatibility_tests: list[dict[str, str]]
    breaking_changes_registry: list[dict[str, str]]
    deprecation_policy: dict[str, Any]
    all_tests_passed: bool
    config_validation_issues: list[str]
