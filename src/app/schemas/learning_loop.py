from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ConversionEventInput(BaseModel):
    event_id: str = Field(..., min_length=3, max_length=160)
    event_time: datetime | None = None
    pixel_id: str = Field(..., min_length=3, max_length=80)
    campaign_id: str = Field(..., min_length=2, max_length=120)
    campaign_name: str = Field(..., min_length=2, max_length=180)
    ad_id: str = Field(..., min_length=2, max_length=120)
    ad_name: str = Field(..., min_length=2, max_length=180)
    creative_id: str = Field(..., min_length=2, max_length=120)
    creative_name: str = Field(..., min_length=2, max_length=180)
    product_name: str = Field(..., min_length=2, max_length=180)
    geo: str = Field("UNKNOWN", max_length=80)
    language: str = Field("auto", max_length=80)
    value: float = Field(0, ge=0)
    currency: str = Field("BRL", min_length=3, max_length=3)
    purchase_count: int = Field(1, ge=1)
    cpa: float = Field(0, ge=0)
    roas: float = Field(0, ge=0)
    connect_rate: float = Field(0, ge=0)
    checkout_rate: float = Field(0, ge=0)
    hook: str = Field("", max_length=260)
    copy_text: str = Field("", max_length=1200)
    creative_pattern: str = Field("", max_length=500)
    final_url: HttpUrl | None = None


class CapiIngestRequest(BaseModel):
    events: list[ConversionEventInput] = Field(..., min_length=1, max_length=100)
    forward_to_meta: bool = False


class CapiEventResult(BaseModel):
    event_id: str
    status: str
    stored: bool
    forwarded_to_meta: bool
    message: str


class CapiIngestResponse(BaseModel):
    received: int
    stored: int
    forwarded: int
    results: list[CapiEventResult]


class LearningLoopRequest(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=180)
    min_roas: float = Field(1.0, ge=0)
    min_purchases: int = Field(1, ge=1)
    max_winners: int = Field(5, ge=1, le=20)
    generate_versions: list[str] = Field(default_factory=lambda: ["V4", "V5", "V6"])
    prepare_war_kit: bool = True


class WinnerInsight(BaseModel):
    creative_id: str
    ad_name: str
    campaign_name: str
    purchases: int
    revenue: float
    avg_roas: float
    avg_cpa: float
    avg_connect_rate: float
    hook: str
    creative_pattern: str
    recommendation: str


class GeneratedVariation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str
    based_on_creative_id: str
    campaign_name: str
    hook: str
    copy_text: str = Field(..., alias="copy")
    image_prompt: str
    video_script: str
    reason: str


class LearningLoopResponse(BaseModel):
    product_name: str
    analyzed_at: datetime
    capi_stable: bool
    total_events_used: int
    winners: list[WinnerInsight]
    generated_variations: list[GeneratedVariation]
    next_actions: list[str]
    warnings: list[str]
    output_folder: str | None = None
