from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


GeoPreset = Literal["LATAM_ESP", "USD_TIER1", "EURO_TIER", "BRASIL", "CUSTOM"]
LanguagePreset = Literal["Spanish_All", "English_All", "Portuguese_All", "Custom"]
OperatorMode = Literal["dry_run", "publish_paused", "publish_active"]


class MetaCreativeInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=2, max_length=120)
    media_url: HttpUrl | None = None
    media_type: Literal["image", "video"] = "image"
    copy_text: str = Field(..., alias="copy", min_length=5, max_length=2000)


class MetaOperatorLaunchRequest(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=180)
    existing_campaign_id: str | None = Field(None, max_length=160)
    pixel_id: str = Field(..., min_length=3, max_length=80)
    landing_page_url: HttpUrl
    affiliate_id: str | None = Field(None, max_length=120)
    geo_preset: GeoPreset = "LATAM_ESP"
    language: LanguagePreset = "Spanish_All"
    custom_countries: list[str] = Field(default_factory=list, max_length=25)
    excluded_countries: list[str] = Field(default_factory=lambda: ["BR"], max_length=25)
    daily_budget_brl: float = Field(25, ge=5, le=5000)
    campaign_model: Literal["V3_ONE_CAMPAIGN_PER_CREATIVE"] = "V3_ONE_CAMPAIGN_PER_CREATIVE"
    optimization_event: Literal["PURCHASE"] = "PURCHASE"
    device: Literal["mobile_only"] = "mobile_only"
    connection: Literal["wifi_only"] = "wifi_only"
    placements_mode: Literal["facebook_instagram_manual"] = "facebook_instagram_manual"
    mode: OperatorMode = "dry_run"
    creatives: list[MetaCreativeInput] = Field(..., min_length=1, max_length=6)
    confirmed_by_user: bool = False
    expected_payload_sha256: str | None = Field(None, min_length=64, max_length=64)


class MetaOperatorGuardrail(BaseModel):
    name: str
    status: Literal["ok", "warning", "blocked"]
    message: str


class MetaOperatorPayloadPreview(BaseModel):
    payload_sha256: str
    plans: list[dict[str, Any]]
    message: str


class MetaOperatorCampaignResult(BaseModel):
    creative_name: str
    campaign_name: str
    adset_name: str
    ad_name: str
    status: str
    dry_run: bool
    meta_campaign_id: str | None = None
    meta_adset_id: str | None = None
    meta_creative_id: str | None = None
    meta_ad_id: str | None = None
    messages: list[str] = Field(default_factory=list)


class MetaOperatorLaunchResponse(BaseModel):
    started_at: datetime
    finished_at: datetime
    operator: str = "Meta AI Campaign Operator"
    mode: OperatorMode
    dry_run: bool
    product_name: str
    geo_preset: GeoPreset
    language: LanguagePreset
    attempted: int
    published: int
    blocked: int
    guardrails: list[MetaOperatorGuardrail]
    payload_preview: MetaOperatorPayloadPreview | None = None
    account_spend_today_brl: float | None = None
    results: list[MetaOperatorCampaignResult]


class MetaOperatorStatusResponse(BaseModel):
    enabled: bool
    dry_run: bool
    autopublish_allowed: bool
    active_launch_allowed: bool
    configured_credentials: bool
    supported_presets: dict[str, dict]
    required_env: list[str]
    production_safety: dict[str, Any] = Field(default_factory=dict)


class MetaOperatorRollbackRequest(BaseModel):
    action: Literal["pause", "delete"] = "pause"
    force_dry_run: bool = True
    confirmed_by_user: bool = False


class MetaOperatorRollbackResponse(BaseModel):
    dry_run: bool
    action: str
    attempted: int
    executed: int
    blocked: bool
    message: str
    results: list[dict[str, Any]] = Field(default_factory=list)
