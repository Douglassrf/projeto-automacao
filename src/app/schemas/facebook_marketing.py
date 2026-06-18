from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

from app.schemas.affiliate import AffiliateReplaceResponse


class MarketingLessonProfile(BaseModel):
    """Conhecimento tático das aulas/material: funil, frequência, oferta e criativo."""

    offer_angle: str = Field("dor + promessa clara + prova + CTA", max_length=180)
    audience_temperature: str = Field("frio", max_length=40)
    creative_style: str = Field("UGC/antes-depois/benefício direto", max_length=120)
    pain_point: str = Field("dor específica e urgente", max_length=160)
    proof_element: str = Field("prova social ou demonstração", max_length=160)
    risk_notes: list[str] = Field(default_factory=list)


class FacebookAdSignal(BaseModel):
    external_id: str | None = Field(None, max_length=120)
    product_name: str = Field(..., min_length=2, max_length=180)
    creative_original: str = Field(..., min_length=5, max_length=10000)
    destination_url: HttpUrl | None = None
    active_ads: int = Field(0, ge=0)
    cpc: float = Field(0, ge=0)
    ctr: float = Field(0, ge=0)
    cpm: float = Field(0, ge=0)
    spend: float = Field(0, ge=0)
    revenue: float = Field(0, ge=0)
    link_clicks: int = Field(0, ge=0)
    landing_page_views: int = Field(0, ge=0)
    checkout_starts: int = Field(0, ge=0)
    purchases: int = Field(0, ge=0)
    lesson_profile: MarketingLessonProfile = Field(default_factory=MarketingLessonProfile)


class V1MarketingRequest(BaseModel):
    threshold_min: int = Field(15, ge=0)
    threshold_max: int = Field(40, ge=1)
    items: list[FacebookAdSignal] = Field(..., min_length=1, max_length=250)


class V1ItemDecision(BaseModel):
    external_id: str | None
    product_name: str
    active_ads: int
    status: str
    marketing_stage: str
    score: float
    decision: str
    recommended_action: str
    reasons: list[str]
    generated_angles: list[str]


class V1MarketingResponse(BaseModel):
    total_received: int
    winners: int
    rejected: int
    decisions: list[V1ItemDecision]


class CampaignBudgetGuardrails(BaseModel):
    daily_budget_brl: float = Field(30, ge=5, le=5000)
    max_daily_budget_brl: float = Field(150, ge=5, le=20000)
    max_campaigns_per_run: int = Field(3, ge=1, le=20)
    require_manual_review: bool = False
    allow_active_launch: bool = False


class CampaignPlanRequest(BaseModel):
    threshold_min: int = Field(15, ge=0)
    threshold_max: int = Field(40, ge=1)
    affiliate_id: str | None = Field("demo-affiliate", max_length=120)
    network: str = Field("generic", min_length=2, max_length=40)
    budget: CampaignBudgetGuardrails = Field(default_factory=CampaignBudgetGuardrails)
    items: list[FacebookAdSignal] = Field(..., min_length=1, max_length=250)


class CampaignPlanItem(BaseModel):
    external_id: str | None
    product_name: str
    campaign_model: str
    priority: int
    action: str
    existing_campaign_id: str | None = Field(None, max_length=160)
    campaign_name: str
    adset_name: str
    ad_name: str
    objective: str
    daily_budget_brl: float
    optimization_goal: str
    billing_event: str = "IMPRESSIONS"
    campaign_status: str = "PAUSED"
    adset_status: str = "PAUSED"
    ad_status: str = "PAUSED"
    promoted_object: str
    audience_notes: list[str]
    targeting: dict = Field(default_factory=dict)
    creative_variations: list[str]
    copy_variations: list[str]
    affiliate: AffiliateReplaceResponse | None = None
    manual_review_required: bool
    automation_notes: list[str] = Field(default_factory=list)


class CampaignPlanResponse(BaseModel):
    generated_at: datetime
    mode: str
    total_items: int
    approved_for_plan: int
    plans: list[CampaignPlanItem]


class V3ExecutionRequest(CampaignPlanRequest):
    publish_to_meta: bool = Field(True, description="Publica via Meta quando credenciais oficiais e META_DRY_RUN=false estiverem configurados.")
    execution_mode: str = Field("automatic_v3", pattern="^(review_only|automatic_v3)$")


class MetaExecutionResult(BaseModel):
    dry_run: bool
    product_name: str
    campaign_model: str
    campaign_name: str
    meta_campaign_id: str | None = None
    meta_adset_id: str | None = None
    meta_creative_id: str | None = None
    meta_ad_id: str | None = None
    status: str
    messages: list[str]


class V3ExecutionResponse(BaseModel):
    started_at: datetime
    finished_at: datetime
    dry_run: bool
    attempted: int
    published: int
    blocked_for_review: int
    results: list[MetaExecutionResult]

class V2CreativeInput(BaseModel):
    ad_name: str = Field(..., min_length=2, max_length=80)
    media_name: str = Field(..., min_length=2, max_length=160)
    media_type: str = Field("image", pattern="^(image|video)$")
    media_url: HttpUrl | None = None


class V2DedicatedSimulationRequest(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=180)
    pixel_id: str = Field(..., min_length=3, max_length=80)
    destination_url: HttpUrl
    primary_text: str = Field(..., min_length=5, max_length=2000)
    daily_budget_brl: float = Field(50, ge=5, le=5000)
    conversion_event: str = Field("Purchase", pattern="^(Purchase|CompleteRegistration|InitiateCheckout)$")
    objective: str = Field("OUTCOME_SALES")
    destination: str = Field("website")
    included_countries: list[str] = Field(default_factory=lambda: ["AR", "CL", "CO", "PE", "MX", "EC"])
    excluded_countries: list[str] = Field(default_factory=lambda: ["BR"])
    language: str = Field("Spanish (All)", max_length=80)
    age_min: int = Field(25, ge=13, le=65)
    genders: list[str] = Field(default_factory=lambda: ["all"])
    mobile_only: bool = True
    wifi_only: bool = True
    publisher_platforms: list[str] = Field(default_factory=lambda: ["facebook", "instagram"])
    removed_placements: list[str] = Field(default_factory=lambda: ["threads", "audience_network", "messenger"])
    flexible_media_disabled: bool = True
    auto_creative_optimizations_disabled: bool = True
    no_end_date: bool = True
    creatives: list[V2CreativeInput] = Field(..., min_length=4, max_length=4)


class V2AdSimulationItem(BaseModel):
    ad_name: str
    media_name: str
    media_type: str
    simulated_ad_id: str
    same_copy: bool
    same_link: bool
    media_original_format: bool
    status: str


class V2DedicatedSimulationResponse(BaseModel):
    campaign_name: str
    adset_name: str
    objective: str
    destination: str
    conversion_event: str
    pixel_id: str
    daily_budget_brl: float
    analysis_window_days: int
    structure_valid: bool
    campaign_status: str
    targeting: dict
    ads: list[V2AdSimulationItem]
    checklist: list[str]
    warnings: list[str]
    simulated: bool = True

class CampaignSubNicheInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    audience_pain: str = Field(..., min_length=2, max_length=220)
    promise_angle: str = Field(..., min_length=2, max_length=220)
    media_direction: str = Field("imagem ou vídeo em formato original", max_length=220)


class ProductMaterialInput(BaseModel):
    pdf_title: str = Field(..., min_length=2, max_length=180)
    landing_page_url: HttpUrl
    checkout_url: HttpUrl | None = None
    affiliate_link: HttpUrl | None = None
    language: str = Field("auto", max_length=80)
    main_copy: str = Field(..., min_length=5, max_length=2000)
    product_description: str = Field(..., min_length=5, max_length=3000)


class CampaignCategoryConfig(BaseModel):
    campaign_type: str = Field(..., pattern="^(V1|V2|V3)$")
    campaign_name: str
    daily_budget_brl: float = Field(..., ge=5, le=10000)
    subniches: list[CampaignSubNicheInput]


class GeneratedAssetBlueprint(BaseModel):
    asset_type: str
    name: str
    prompt_or_brief: str
    format_rule: str
    status: str = "blueprint_ready"


class CampaignAdUnitPlan(BaseModel):
    adset_name: str
    ad_name: str
    subniche: str
    objective: str = "OUTCOME_SALES"
    destination: str = "website"
    conversion_event: str = "Purchase"
    pixel_id: str
    audience_type: str
    countries: list[str]
    excluded_countries: list[str]
    language: str
    placements: list[str]
    removed_placements: list[str]
    device: str
    connection: str
    primary_text: str
    final_link: str
    assets: list[GeneratedAssetBlueprint]
    rules: list[str]


class ProductCampaignSuiteRequest(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=180)
    pixel_id: str = Field(..., min_length=3, max_length=80)
    material: ProductMaterialInput
    countries: list[str] = Field(default_factory=lambda: ["AR", "CL", "CO", "PE", "MX", "EC"])
    excluded_countries: list[str] = Field(default_factory=lambda: ["BR"])
    language: str = Field("auto_by_winning_ad", max_length=80)
    publisher_platforms: list[str] = Field(default_factory=lambda: ["facebook", "instagram"])
    removed_placements: list[str] = Field(default_factory=lambda: ["threads", "audience_network", "messenger"])
    device: str = Field("mobile_only")
    connection: str = Field("wifi_only")
    v1_subniches: list[CampaignSubNicheInput] = Field(..., min_length=5, max_length=5)
    v2_subniches: list[CampaignSubNicheInput] = Field(..., min_length=4, max_length=4)
    v3_subniches: list[CampaignSubNicheInput] = Field(..., min_length=5, max_length=5)
    v1_daily_budget_brl: float = Field(25, ge=5, le=10000)
    v2_daily_budget_brl: float = Field(50, ge=5, le=10000)
    v3_daily_budget_brl: float = Field(25, ge=5, le=10000)
    dry_run: bool = True


class ProductCampaignCategoryPlan(BaseModel):
    campaign_type: str
    campaign_name: str
    daily_budget_brl: float
    structural_rule: str
    total_adsets: int
    total_ads: int
    adsets: list[CampaignAdUnitPlan]


class ProductCampaignSuiteResponse(BaseModel):
    product_name: str
    generated_at: datetime
    dry_run: bool
    total_campaigns: int
    total_adsets: int
    total_ads: int
    campaigns: list[ProductCampaignCategoryPlan]
    validation_checklist: list[str]
    warnings: list[str]
