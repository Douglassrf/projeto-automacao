from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DecisionLogCreate(BaseModel):
    user_id: int | None = None
    campaign_id: str = Field(default="manual", max_length=120)
    product_name: str = Field(default="", max_length=180)
    reason_code: str = Field(..., max_length=80)
    metric_name: str = Field(default="", max_length=80)
    metric_value: float = 0
    threshold_value: float | None = None
    severity: str = Field(default="info", pattern="^(success|warning|danger|info)$")
    tag_label: str = Field(default="Otimização realizada", max_length=80)
    action_taken: str = Field(default="monitor", max_length=120)
    reasoning: str = ""
    metadata_json: str = "{}"


class DecisionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    timestamp: datetime
    campaign_id: str
    product_name: str
    reason_code: str
    metric_name: str
    metric_value: float
    threshold_value: float | None
    severity: str
    tag_label: str
    action_taken: str
    reasoning: str
    metadata_json: str


class DecisionLogImportResponse(BaseModel):
    rows_read: int
    decisions_created: int
    campaigns_evaluated: int
    warnings: list[str] = []


class DecisionHealthSummary(BaseModel):
    total: int
    success: int
    warning: int
    danger: int
    info: int
    status: str
    headline: str
    next_action: str
