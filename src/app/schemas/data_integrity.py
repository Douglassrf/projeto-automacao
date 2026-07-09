from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DataIntegrityResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    strict_validation: bool
    overall_status: str
    consistency_checks: list[dict[str, Any]]
    invalid_records: list[dict[str, Any]]
    invalid_record_count: int
    backup_restore_integrity: dict[str, Any]
    config_validation_issues: list[str]
