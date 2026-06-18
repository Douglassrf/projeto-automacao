from pydantic import BaseModel, Field, HttpUrl


class AffiliateReplaceRequest(BaseModel):
    ad_id: int | str | None = Field(None, description="ID da análise/anúncio usado no log de atividade")
    creative_original: str = Field(..., min_length=5, description="Texto, HTML ou copy do criativo original")
    network: str = Field("generic", min_length=2, max_length=40)
    user_affiliate_id: str | None = Field(None, max_length=120)
    destination_url: HttpUrl | None = None
    fallback_affiliate_link: HttpUrl | None = None


class AffiliateActivity(BaseModel):
    timestamp: str
    ad_id: int | str
    original_link: str
    affiliate_link: str


class AffiliateReplaceResponse(BaseModel):
    network: str
    original_link: str
    affiliate_link: str
    creative_updated: str
    provider_status: str
    message: str
    activity_logged: bool = True
