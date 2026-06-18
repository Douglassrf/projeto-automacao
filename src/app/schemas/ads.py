from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AdAnalysisRequest(BaseModel):
    user_id: int | None = None
    product_name: str = Field(..., min_length=2, max_length=180)
    active_ads: int = Field(0, ge=0)
    cpc: float = Field(0, ge=0)
    link_clicks: int = Field(0, ge=0)
    landing_page_views: int = Field(0, ge=0)
    checkout_starts: int = Field(0, ge=0)
    purchases: int = Field(0, ge=0)


class AdAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    product_name: str
    active_ads: int
    cpc: float
    link_clicks: int
    landing_page_views: int
    checkout_starts: int
    purchases: int
    connect_rate: float
    checkout_rate: float
    purchase_rate: float
    score: float
    status: str
    preview_url: str
    edited_link: str
    insight: str
    created_at: datetime


class DashboardSummary(BaseModel):
    total_analyses: int
    winners: int
    average_score: float
    average_connect_rate: float
    latest: list[AdAnalysisResponse]
