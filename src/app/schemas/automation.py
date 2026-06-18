from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

from app.schemas.ads import AdAnalysisResponse
from app.schemas.affiliate import AffiliateReplaceResponse


class FeedAdItem(BaseModel):
    external_id: str | None = Field(None, max_length=120)
    product_name: str = Field(..., min_length=2, max_length=180)
    creative_original: str = Field(..., min_length=5, max_length=10000)
    destination_url: HttpUrl | None = None
    active_ads: int = Field(0, ge=0)
    cpc: float = Field(0, ge=0)
    link_clicks: int = Field(0, ge=0)
    landing_page_views: int = Field(0, ge=0)
    checkout_starts: int = Field(0, ge=0)
    purchases: int = Field(0, ge=0)


class AutomationAffiliateConfig(BaseModel):
    network: str = Field("generic", min_length=2, max_length=40)
    user_affiliate_id: str | None = Field(None, max_length=120)
    fallback_affiliate_link: HttpUrl | None = None


class BatchProcessRequest(BaseModel):
    threshold_min: int = Field(15, ge=0, description="Mínimo de anúncios ativos para considerar vencedor")
    threshold_max: int = Field(40, ge=1, description="Marco superior para classificação de alta força")
    affiliate: AutomationAffiliateConfig = Field(default_factory=AutomationAffiliateConfig)
    items: list[FeedAdItem] = Field(..., min_length=1, max_length=250)


class BatchProcessItemResult(BaseModel):
    external_id: str | None
    product_name: str
    active_ads: int
    decision: str
    reason: str
    analysis: AdAnalysisResponse
    affiliate: AffiliateReplaceResponse | None = None


class BatchProcessResponse(BaseModel):
    started_at: datetime
    finished_at: datetime
    total_received: int
    analyzed: int
    winners: int
    optimized: int
    rejected: int
    threshold_min: int
    threshold_max: int
    results: list[BatchProcessItemResult]
