from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DomainTrackedInfo(BaseModel):
    domain: str
    source: str
    mission: str


class AutonomousOperationsResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    require_all_domains: bool
    verdict: str
    autonomous_operations_ready: bool
    blocking_issues: list[str]
    blocking_issue_count: int
    domain_status: dict[str, str]
    domains_ok: int
    domains_total: int
    domains_tracked: list[dict[str, str]]
    evidence: dict[str, Any]
    config_validation_issues: list[str]
