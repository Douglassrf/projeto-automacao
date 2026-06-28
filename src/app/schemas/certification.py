from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.system_alerts import AlertEventResponse


class MissionCoveredInfo(BaseModel):
    mission: str
    name: str
    summary: str


class DependencyAuditSummary(BaseModel):
    total_declared: int
    pinned_count: int
    unpinned_count: int
    missing_count: int
    version_mismatch_count: int
    issues: list[str]


class CertificationResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    strict_mode: bool
    config_validation_issues: list[str]
    diagnostics_status: str
    diagnostics_summary: dict[str, int]
    active_alerts_count: int
    active_alerts: list[AlertEventResponse]
    dependency_audit_summary: DependencyAuditSummary
    queue_recovery: dict[str, Any]
    resource_usage: dict[str, Any]
    missions_covered: list[MissionCoveredInfo]
    blocking_issues: list[str]
    platinum_certified: bool
