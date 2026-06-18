from pydantic import BaseModel, Field, HttpUrl
from typing import Literal


class SiteOfferInput(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=120)
    niche: str = Field(..., min_length=2, max_length=80)
    target_geo: str = Field(default="LATAM ESP")
    language: str = Field(default="es")
    headline: str = Field(..., min_length=8, max_length=180)
    subheadline: str = Field(..., min_length=8, max_length=260)
    benefits: list[str] = Field(default_factory=list, max_length=8)
    pain_points: list[str] = Field(default_factory=list, max_length=8)
    social_proof: str | None = Field(default=None, max_length=240)
    guarantee: str | None = Field(default=None, max_length=160)
    price_anchor: str | None = Field(default=None, max_length=120)
    checkout_url: str = Field(..., min_length=8, max_length=500)
    cta_text: str = Field(default="Quero acessar agora", max_length=80)


class SiteDeployOptions(BaseModel):
    provider: Literal["local", "github_vercel", "vercel", "netlify"] = "local"
    dry_run: bool = True
    repository_name: str | None = Field(default=None, max_length=120)
    branch: str = Field(default="main", max_length=60)


class SiteGenerateRequest(BaseModel):
    offer: SiteOfferInput
    template: Literal["direct_response", "ebook", "checkout_bridge"] = "direct_response"
    deploy: SiteDeployOptions = Field(default_factory=SiteDeployOptions)


class SiteGenerateResponse(BaseModel):
    product_name: str
    template: str
    output_dir: str
    preview_path: str
    files: list[str]
    deploy_provider: str
    deploy_status: str
    deploy_url: str | None = None
    deploy_payload_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
