from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ProductionExcellenceResponse(BaseModel):
    generated_at: datetime | None = None
    dashboard_status: str | None = None
    services: list[dict[str, Any]] | None = None
    resource_consumption: dict[str, Any] | None = None
    latency: dict[str, Any] | None = None
    availability: dict[str, Any] | None = None
    incident_history: list[dict[str, Any]] | None = None
    realtime_refresh_seconds: int | None = None


class ProductionExcellenceFullResponse(BaseModel):
    monitoring_center: dict[str, Any]
    service_levels: dict[str, Any]
    capacity_planning: dict[str, Any]
    operational_analytics: dict[str, Any]
    continuous_compliance: dict[str, Any]
    knowledge_center: dict[str, Any]
    maintenance_planner: dict[str, Any]
    executive_governance: dict[str, Any]
    production_certification: dict[str, Any]
