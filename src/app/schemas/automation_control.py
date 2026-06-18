from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AutomationLevel = Literal[0, 1, 2]
AutomationAction = Literal["notify_only", "pause_campaign", "pause_adset", "scale_budget"]
AutomationTarget = Literal["campaign", "adset"]


class AutomationControlStatusResponse(BaseModel):
    automation_level: AutomationLevel
    dry_run: bool
    meta_credentials_configured: bool
    kill_switch_enabled: bool
    daily_spend_limit_brl: float
    level_description: str
    allowed_actions: list[str]
    required_env_for_level_1: list[str]
    required_env_for_level_2: list[str]


class ApplySuggestionRequest(BaseModel):
    campaign_id: str = Field(..., min_length=2, max_length=160)
    adset_id: str | None = Field(None, max_length=160)
    action: AutomationAction = "notify_only"
    target: AutomationTarget = "campaign"
    reason_code: str = Field(..., min_length=2, max_length=120)
    metric_name: str = Field(..., min_length=2, max_length=80)
    metric_value: float = 0
    threshold_value: float | None = None
    daily_spend_brl: float = Field(0, ge=0)
    current_purchases: int = Field(0, ge=0)
    new_daily_budget_brl: float | None = Field(None, ge=1, le=5000)
    confirmed_by_user: bool = False
    force_dry_run: bool = True
    reasoning: str | None = Field(None, max_length=1000)


class ApplySuggestionResponse(BaseModel):
    timestamp: datetime
    automation_level: AutomationLevel
    action_requested: AutomationAction
    action_executed: bool
    dry_run: bool
    blocked: bool
    blocked_reason: str | None = None
    campaign_id: str
    adset_id: str | None = None
    meta_response: dict
    decision_log_id: int | None = None
    reasoning: str


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = Field("manual_toggle", max_length=240)


class KillSwitchResponse(BaseModel):
    enabled: bool
    changed_at: datetime
    reason: str
