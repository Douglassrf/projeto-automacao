from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["green", "yellow", "red", "info"]
ActionRecommendation = Literal[
    "monitor",
    "pause_campaign",
    "reduce_budget_50",
    "scale_budget_20",
    "scale_budget",
    "decrease_bid",
    "generate_new_assets",
    "activate_capi_fallback",
    "fix_landing_page",
]


class CampaignCreateRequest(BaseModel):
    internal_campaign_id: str = Field(..., min_length=2, max_length=160)
    meta_campaign_id: str = Field("", max_length=160)
    meta_adset_id: str = Field("", max_length=160)
    product_id: str = Field("", max_length=160)
    product_name: str = Field("", max_length=180)
    strategy_version: Literal["V1", "V2", "V3", "V4", "V5", "V6"] = "V1"
    status: str = Field("ACTIVE", max_length=40)
    desired_status: str = Field("ACTIVE", max_length=40)
    real_status: str = Field("UNKNOWN", max_length=40)
    last_state_sync_reason: str = Field("", max_length=1000)
    daily_budget: float = Field(0, ge=0)
    spend_today: float = Field(0, ge=0)
    desired_budget: float = Field(0, ge=0)
    real_budget: float = Field(0, ge=0)
    budget_drift_detected: bool = False
    currency_code: str = Field("BRL", max_length=8)
    currency_ad_account: str = Field("BRL", max_length=8)
    currency_sales: str = Field("EUR", max_length=8)
    target_cpa: float = Field(0, ge=0)
    target_roas: float = Field(1, ge=0)


class CampaignResponse(CampaignCreateRequest):
    id: int
    created_at: datetime
    updated_at: datetime


class CampaignMetricCreateRequest(BaseModel):
    internal_campaign_id: str | None = Field(None, max_length=160)
    meta_campaign_id: str | None = Field(None, max_length=160)
    ctr: float = Field(0, ge=0)
    cpc: float = Field(0, ge=0)
    cpm: float = Field(0, ge=0)
    spend: float = Field(0, ge=0)
    purchases: int = Field(0, ge=0)
    cost_per_purchase: float = Field(0, ge=0)
    roas: float = Field(0, ge=0)
    revenue_amount: float = Field(0, ge=0)
    revenue_currency: str = Field("EUR", max_length=8)
    exchange_rate_to_brl: float = Field(0, ge=0)
    revenue_brl: float = Field(0, ge=0)
    unified_roas_brl: float = Field(0, ge=0)
    connect_rate: float = Field(0, ge=0)
    checkout_rate: float = Field(0, ge=0)
    capi_status: Literal["ok", "error", "degraded", "fallback"] = "ok"
    source: Literal["manual", "csv", "meta_api", "dry_run"] = "manual"


class CampaignMetricResponse(CampaignMetricCreateRequest):
    id: int
    campaign_id: int
    date: datetime
    created_at: datetime


class FinancialMetricCreateRequest(BaseModel):
    internal_campaign_id: str | None = Field(None, max_length=160)
    meta_campaign_id: str | None = Field(None, max_length=160)
    spend_brl: float = Field(0, ge=0)
    revenue_amount: float = Field(0, ge=0)
    revenue_currency: str = Field("EUR", max_length=8)
    exchange_rate: float = Field(0, ge=0)
    exchange_rate_source: str = Field("manual_or_env", max_length=80)
    raw_payload: dict = Field(default_factory=dict)


class FinancialMetricResponse(FinancialMetricCreateRequest):
    id: int
    campaign_id: int
    revenue_brl: float
    calculated_roas_brl: float
    fx_validated: bool
    date: datetime
    created_at: datetime


class AdLibraryBenchmarkCreateRequest(BaseModel):
    niche: str = Field(..., min_length=2, max_length=120)
    geo: str = Field("", max_length=80)
    language: str = Field("", max_length=80)
    creative_pattern: str = Field("", max_length=180)
    hook_pattern: str = Field("", max_length=180)
    days_active: int = Field(0, ge=0)
    estimated_strength_score: float = Field(0, ge=0, le=100)
    benchmark_ctr: float = Field(1.0, ge=0)
    source_ad_id: str = Field("", max_length=160)


class AdLibraryBenchmarkResponse(AdLibraryBenchmarkCreateRequest):
    id: int
    captured_at: datetime


class PerformanceTicketResponse(BaseModel):
    id: int
    campaign_id: int
    severity: Severity
    reason_code: str
    action_recommended: ActionRecommendation
    reasoning: str
    status: str
    created_at: datetime


class EvaluateCampaignRequest(BaseModel):
    internal_campaign_id: str | None = Field(None, max_length=160)
    meta_campaign_id: str | None = Field(None, max_length=160)
    niche: str | None = Field(None, max_length=120)
    geo: str | None = Field(None, max_length=80)
    dry_run: bool = True


class CampaignDecisionResponse(BaseModel):
    campaign: CampaignResponse
    latest_metrics: CampaignMetricResponse | None
    benchmark_ctr: float | None
    health_color: Severity
    tickets_opened: list[PerformanceTicketResponse]
    recommended_actions: list[ActionRecommendation]
    reasoning: str


class DecisionLoopRequest(BaseModel):
    dry_run: bool = True
    meta_cpa_ideal: float | None = Field(None, ge=0)
    test_budget_brl: float | None = Field(None, ge=0)
    scale_budget_brl: float | None = Field(None, ge=0)
    limit: int = Field(50, ge=1, le=500)


class DecisionLoopActionResponse(BaseModel):
    campaign_pk: int
    internal_campaign_id: str
    meta_campaign_id: str
    meta_adset_id: str
    spend_real: float
    daily_budget: float
    desired_budget: float = 0
    real_budget: float = 0
    cpa: float
    target_cpa: float
    action: str
    executed: bool
    dry_run: bool
    reason_code: str
    reasoning: str
    meta_response: dict


class DecisionLoopResponse(BaseModel):
    processed: int
    actions_taken: int
    dry_run: bool
    results: list[DecisionLoopActionResponse]


class IntelligenceHealthResponse(BaseModel):
    campaigns: int
    metrics: int
    benchmarks: int
    open_tickets: int
    schema_keys: dict[str, str]
    agent_visibility: str

class MetaActionProposalRequest(BaseModel):
    internal_campaign_id: str | None = Field(None, max_length=160)
    meta_campaign_id: str | None = Field(None, max_length=160)
    action: Literal["pause_campaign", "pause_adset", "decrease_bid", "scale_budget", "notify_only"]
    target: Literal["campaign", "adset"] = "campaign"
    new_daily_budget_brl: float | None = Field(None, ge=0)
    reasoning: str = Field("", max_length=800)


class MetaActionApprovalRequest(BaseModel):
    payload_hash: str = Field(..., min_length=8, max_length=128)
    confirmed_by_user: bool = False
    approved_by: str = Field("dashboard_user", max_length=120)
    dry_run: bool = True


class MetaActionExecutionRequest(BaseModel):
    confirmed_by_user: bool = False
    dry_run: bool = True


class MetaDecisionContextResponse(BaseModel):
    action_id: int
    campaign_id: int
    meta_campaign_id: str
    action: str
    status: str
    reason: str
    payload_hash: str
    ctr: float
    cpa: float
    roas: float
    unified_roas_brl: float = 0
    revenue_brl: float = 0
    revenue_currency: str = "EUR"
    exchange_rate_to_brl: float = 0
    spend: float
    daily_budget: float
    desired_budget: float
    real_budget: float
    currency_ad_account: str = "BRL"
    currency_sales: str = "EUR"
    budget_drift_detected: bool
    desired_status: str
    real_status: str
    reasoning: str
    created_at: datetime


class MetaActionResponse(BaseModel):
    id: int
    request_key: str
    campaign_id: int
    meta_campaign_id: str
    meta_adset_id: str
    action: str
    target: str
    proposed_payload: dict
    payload_hash: str
    status: str
    requested_by: str
    approved_by: str
    meta_response: dict
    created_at: datetime


class CampaignStateSyncResponse(BaseModel):
    campaign_pk: int
    internal_campaign_id: str
    meta_campaign_id: str
    desired_status: str
    real_status: str
    divergence_detected: bool
    reason: str

class MetaCampaignSyncRequest(BaseModel):
    limit: int = Field(100, ge=1, le=500)
    dry_run: bool = True


class MetaCampaignSyncItem(BaseModel):
    campaign_pk: int
    internal_campaign_id: str
    meta_campaign_id: str
    name: str
    real_status: str
    desired_status: str
    spend_today: float
    daily_budget: float
    desired_budget: float
    real_budget: float
    currency_ad_account: str = "BRL"
    currency_sales: str = "EUR"
    budget_drift_detected: bool
    drift_detected: bool
    last_decision: str


class MetaCampaignSyncResponse(BaseModel):
    processed: int
    created: int
    updated: int
    drift_detected: int
    dry_run: bool
    items: list[MetaCampaignSyncItem]


class ScalingRuleCreateRequest(BaseModel):
    internal_campaign_id: str | None = Field(None, max_length=160)
    meta_campaign_id: str | None = Field(None, max_length=160)
    min_roas_threshold: float = Field(2.0, ge=0)
    excellent_roas_threshold: float = Field(4.0, ge=0)
    standard_increment_percentage: int = Field(10, ge=1, le=50)
    increment_percentage: int = Field(20, ge=1, le=50)
    max_budget_cap: float = Field(5000.0, ge=0)
    cooldown_days: int = Field(3, ge=0, le=30)
    min_sales_volume: int = Field(1, ge=0)
    max_cpa_brl: float = Field(0, ge=0)
    min_ctr: float = Field(0, ge=0)
    is_active: bool = True


class ScalingRuleResponse(ScalingRuleCreateRequest):
    id: int
    campaign_id: int
    last_scale_date: datetime | None
    created_at: datetime
    updated_at: datetime


class ManualRevenueEntryCreateRequest(BaseModel):
    internal_campaign_id: str | None = Field(None, max_length=160)
    meta_campaign_id: str | None = Field(None, max_length=160)
    revenue_amount: float = Field(..., gt=0)
    currency: str = Field("EUR", max_length=8)
    exchange_rate_to_brl: float = Field(0, ge=0)
    sales_count: int = Field(1, ge=1)
    notes: str = Field("", max_length=500)
    created_by: str = Field("manual", max_length=120)


class ManualRevenueEntryResponse(ManualRevenueEntryCreateRequest):
    id: int
    campaign_id: int
    revenue_brl: float
    date_reference: datetime
    created_at: datetime


class IntelligentScalingResponse(BaseModel):
    campaign_pk: int
    internal_campaign_id: str
    meta_campaign_id: str
    current_budget_brl: float
    proposed_budget_brl: float
    increment_percentage: int
    roas_brl: float
    sales_volume: int
    action: str
    reason_code: str
    reasoning: str
    action_id: int | None = None
    status: str


class IntelligentScalingRunResponse(BaseModel):
    processed: int
    proposed: int
    dry_run: bool
    results: list[IntelligentScalingResponse]
