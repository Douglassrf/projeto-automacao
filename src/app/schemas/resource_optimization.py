from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ResourceOptimizationResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    enable_rebalance: bool
    load_balance_recommendations: list[str]
    queue_optimization: dict[str, Any]
    waste_reduction: dict[str, Any]
    queue_health: dict[str, Any]
    disk_usage: dict[str, Any]
    config_validation_issues: list[str]
