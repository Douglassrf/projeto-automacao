from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ModuleTrackedInfo(BaseModel):
    module: str
    mission: str
    label: str


class GlobalProjectState(BaseModel):
    overall_status: str
    platinum_certified: bool
    diagnostics_status: str
    modules_tracked: int
    modules_healthy: int
    modules_health: dict[str, str]


class StabilityIndicators(BaseModel):
    diagnostics_status: str
    diagnostics_summary: dict[str, int]
    active_alerts_count: int
    queue_healthy: bool
    queue_recovery_healthy: bool
    stuck_jobs_count: int
    starving_jobs_count: int
    recoverable_now: int
    requires_external_action: int


class PerformanceIndicators(BaseModel):
    cache_backend: str
    cache_hit_rate: float
    cache_size: int
    cache_live_size: int
    cache_hits: int
    cache_misses: int
    queue_per_queue: dict[str, Any]
    queue_unhealthy_queues: list[str]
    disk_total_size_mb: float
    disk_directories: dict[str, Any]


class RiskIndicators(BaseModel):
    risk_count: int
    risks: list[str]
    dependency_missing_count: int
    dependency_version_mismatch_count: int
    dependency_unpinned_count: int
    config_validation_issue_count: int
    blocking_issue_count: int
    disk_total_size_mb: float


class OperationalIntelligenceResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    include_unpinned_in_risk: bool
    global_project_state: GlobalProjectState
    stability: StabilityIndicators
    performance: PerformanceIndicators
    risk_indicators: RiskIndicators
    modules_tracked: list[ModuleTrackedInfo]
