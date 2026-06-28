from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CurrentMetrics(BaseModel):
    timestamp: str
    cpu_load_percent: float | None
    memory_used_percent: float | None
    storage_used_percent: float
    disk_free_mb: float
    managed_storage_mb: float
    disk_status: str


class Trends(BaseModel):
    cpu: str
    memory: str
    storage: str


class DegradationReport(BaseModel):
    overall_status: str
    snapshot_count: int
    gradual_degradation_areas: list[str]
    trends: dict[str, str]
    predictive_alert_count: int


class PredictiveHealthResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    predictive_alerts_enabled: bool
    current_metrics: dict[str, Any]
    trends: dict[str, str]
    metric_history: list[dict[str, Any]]
    predictive_alerts: list[str]
    degradation_report: dict[str, Any]
    config_validation_issues: list[str]
