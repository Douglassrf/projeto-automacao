from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="Demo User")
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    access_level: Mapped[str] = mapped_column(String(10), default="V1")
    hashed_password: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    analyses: Mapped[list["AdAnalysis"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AdAnalysis(Base):
    __tablename__ = "ad_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(180), index=True)
    active_ads: Mapped[int] = mapped_column(Integer, default=0)
    cpc: Mapped[float] = mapped_column(Float, default=0)
    link_clicks: Mapped[int] = mapped_column(Integer, default=0)
    landing_page_views: Mapped[int] = mapped_column(Integer, default=0)
    checkout_starts: Mapped[int] = mapped_column(Integer, default=0)
    purchases: Mapped[int] = mapped_column(Integer, default=0)
    connect_rate: Mapped[float] = mapped_column(Float, default=0)
    checkout_rate: Mapped[float] = mapped_column(Float, default=0)
    purchase_rate: Mapped[float] = mapped_column(Float, default=0)
    score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="TESTE")
    preview_url: Mapped[str] = mapped_column(String(255), default="")
    edited_link: Mapped[str] = mapped_column(String(255), default="")
    insight: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    user: Mapped[User | None] = relationship(back_populates="analyses")


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    campaign_id: Mapped[str] = mapped_column(String(120), default="manual", index=True)
    product_name: Mapped[str] = mapped_column(String(180), default="")
    reason_code: Mapped[str] = mapped_column(String(80), index=True)
    metric_name: Mapped[str] = mapped_column(String(80), default="")
    metric_value: Mapped[float] = mapped_column(Float, default=0)
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="info", index=True)
    tag_label: Mapped[str] = mapped_column(String(80), default="Otimização realizada")
    action_taken: Mapped[str] = mapped_column(String(120), default="monitor")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class QueueJob(Base):
    __tablename__ = "queue_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    queue_name: Mapped[str] = mapped_column(String(80), default="default", index=True)
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str] = mapped_column(Text, default="")
    locked_by: Mapped[str] = mapped_column(String(120), default="")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Missao 42 - Gerenciador Inteligente de Filas: backoff exponencial.
    # Quando status="retry", claim() so reclama o job se next_attempt_at for
    # nulo ou <= agora. None para jobs que nunca falharam ou que morreram
    # (sem mais tentativas) - nesses casos o campo nao tem efeito.
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True)


class ContentWorkflow(Base):
    __tablename__ = "content_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(220), index=True)
    platform: Mapped[str] = mapped_column(String(80), default="Instagram")
    content_type: Mapped[str] = mapped_column(String(40), default="post")
    status: Mapped[str] = mapped_column(String(40), default="CREATED", index=True)
    draft_json: Mapped[str] = mapped_column(Text, default="{}")
    approval_notes: Mapped[str] = mapped_column(Text, default="")
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True)

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    internal_campaign_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    meta_campaign_id: Mapped[str] = mapped_column(String(160), unique=True, index=True, default="")
    meta_adset_id: Mapped[str] = mapped_column(String(160), default="", index=True)
    product_id: Mapped[str] = mapped_column(String(160), default="")
    product_name: Mapped[str] = mapped_column(String(180), default="")
    strategy_version: Mapped[str] = mapped_column(String(20), default="V1", index=True)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", index=True)
    daily_budget: Mapped[float] = mapped_column(Float, default=0)
    spend_today: Mapped[float] = mapped_column(Float, default=0)
    desired_budget: Mapped[float] = mapped_column(Float, default=0)
    real_budget: Mapped[float] = mapped_column(Float, default=0)
    budget_drift_detected: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(8), default="BRL")
    currency_ad_account: Mapped[str] = mapped_column(String(8), default="BRL")
    currency_sales: Mapped[str] = mapped_column(String(8), default="EUR")
    desired_status: Mapped[str] = mapped_column(String(40), default="ACTIVE", index=True)
    real_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    last_state_sync_reason: Mapped[str] = mapped_column(Text, default="")
    target_cpa: Mapped[float] = mapped_column(Float, default=0)
    target_roas: Mapped[float] = mapped_column(Float, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True)

    metrics: Mapped[list["CampaignMetric"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    tickets: Mapped[list["PerformanceTicket"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    financial_metrics: Mapped[list["FinancialMetric"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    scaling_rules: Mapped[list["ScalingRule"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    manual_revenue_entries: Mapped[list["ManualRevenueEntry"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class FinancialMetric(Base):
    __tablename__ = "financial_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    spend_brl: Mapped[float] = mapped_column(Float, default=0)
    revenue_amount: Mapped[float] = mapped_column(Float, default=0)
    revenue_currency: Mapped[str] = mapped_column(String(8), default="EUR", index=True)
    exchange_rate: Mapped[float] = mapped_column(Float, default=0)
    revenue_brl: Mapped[float] = mapped_column(Float, default=0)
    calculated_roas_brl: Mapped[float] = mapped_column(Float, default=0)
    exchange_rate_source: Mapped[str] = mapped_column(String(80), default="manual_or_env")
    fx_validated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    raw_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    campaign: Mapped[Campaign] = relationship(back_populates="financial_metrics")


class ScalingRule(Base):
    __tablename__ = "scaling_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    meta_campaign_id: Mapped[str] = mapped_column(String(160), default="", index=True)
    min_roas_threshold: Mapped[float] = mapped_column(Float, default=2.0)
    excellent_roas_threshold: Mapped[float] = mapped_column(Float, default=4.0)
    standard_increment_percentage: Mapped[int] = mapped_column(Integer, default=10)
    increment_percentage: Mapped[int] = mapped_column(Integer, default=20)
    max_budget_cap: Mapped[float] = mapped_column(Float, default=5000.0)
    cooldown_days: Mapped[int] = mapped_column(Integer, default=3)
    last_scale_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    min_sales_volume: Mapped[int] = mapped_column(Integer, default=1)
    max_cpa_brl: Mapped[float] = mapped_column(Float, default=0)
    min_ctr: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True)

    campaign: Mapped[Campaign] = relationship(back_populates="scaling_rules")


class ManualRevenueEntry(Base):
    __tablename__ = "manual_revenue_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    meta_campaign_id: Mapped[str] = mapped_column(String(160), default="", index=True)
    revenue_amount: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="EUR", index=True)
    exchange_rate_to_brl: Mapped[float] = mapped_column(Float, default=0)
    revenue_brl: Mapped[float] = mapped_column(Float, default=0)
    sales_count: Mapped[int] = mapped_column(Integer, default=1)
    date_reference: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    campaign: Mapped[Campaign] = relationship(back_populates="manual_revenue_entries")


class CampaignMetric(Base):
    __tablename__ = "campaign_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    ctr: Mapped[float] = mapped_column(Float, default=0)
    cpc: Mapped[float] = mapped_column(Float, default=0)
    cpm: Mapped[float] = mapped_column(Float, default=0)
    spend: Mapped[float] = mapped_column(Float, default=0)
    purchases: Mapped[int] = mapped_column(Integer, default=0)
    cost_per_purchase: Mapped[float] = mapped_column(Float, default=0)
    roas: Mapped[float] = mapped_column(Float, default=0)
    revenue_amount: Mapped[float] = mapped_column(Float, default=0)
    revenue_currency: Mapped[str] = mapped_column(String(8), default="EUR")
    exchange_rate_to_brl: Mapped[float] = mapped_column(Float, default=0)
    revenue_brl: Mapped[float] = mapped_column(Float, default=0)
    unified_roas_brl: Mapped[float] = mapped_column(Float, default=0)
    connect_rate: Mapped[float] = mapped_column(Float, default=0)
    checkout_rate: Mapped[float] = mapped_column(Float, default=0)
    capi_status: Mapped[str] = mapped_column(String(40), default="ok")
    source: Mapped[str] = mapped_column(String(40), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    campaign: Mapped[Campaign] = relationship(back_populates="metrics")


class AdLibraryBenchmark(Base):
    __tablename__ = "ad_library_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    niche: Mapped[str] = mapped_column(String(120), index=True)
    geo: Mapped[str] = mapped_column(String(80), default="", index=True)
    language: Mapped[str] = mapped_column(String(80), default="", index=True)
    creative_pattern: Mapped[str] = mapped_column(String(180), default="")
    hook_pattern: Mapped[str] = mapped_column(String(180), default="")
    days_active: Mapped[int] = mapped_column(Integer, default=0)
    estimated_strength_score: Mapped[float] = mapped_column(Float, default=0)
    benchmark_ctr: Mapped[float] = mapped_column(Float, default=1.0)
    source_ad_id: Mapped[str] = mapped_column(String(160), default="")
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class PerformanceTicket(Base):
    __tablename__ = "performance_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="yellow", index=True)
    reason_code: Mapped[str] = mapped_column(String(100), index=True)
    action_recommended: Mapped[str] = mapped_column(String(180), default="monitor")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    campaign: Mapped[Campaign] = relationship(back_populates="tickets")


class MetaActionRequest(Base):
    __tablename__ = "meta_action_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    meta_campaign_id: Mapped[str] = mapped_column(String(160), default="", index=True)
    meta_adset_id: Mapped[str] = mapped_column(String(160), default="", index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target: Mapped[str] = mapped_column(String(40), default="campaign")
    proposed_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    payload_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending_approval", index=True)
    requested_by: Mapped[str] = mapped_column(String(120), default="ai_agency_operator")
    approved_by: Mapped[str] = mapped_column(String(120), default="")
    executed_response_json: Mapped[str] = mapped_column(Text, default="{}")
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    campaign: Mapped[Campaign] = relationship()
