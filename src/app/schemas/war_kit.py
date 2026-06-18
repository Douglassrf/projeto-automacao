from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class ProductDNAInput(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=180)
    niche: str = Field(..., min_length=2, max_length=120)
    offer_promise: str = Field(..., min_length=5, max_length=300)
    target_avatar: str = Field(..., min_length=5, max_length=400)
    main_pain: str = Field(..., min_length=5, max_length=300)
    desired_transformation: str = Field(..., min_length=5, max_length=300)
    ticket_price: float = Field(0, ge=0)
    pixel_id: str = Field(..., min_length=3, max_length=80)
    landing_page_url: HttpUrl
    checkout_url: HttpUrl | None = None
    affiliate_link: HttpUrl | None = None
    language: str = Field("auto_by_winning_ad", max_length=80)
    geo_preset: str = Field("LATAM_ESP", pattern="^(LATAM_ESP|USD_TIER_1|EURO_TIER|BRAZIL|CUSTOM)$")
    countries: list[str] = Field(default_factory=lambda: ["AR", "CL", "CO", "PE", "MX", "EC"])
    excluded_countries: list[str] = Field(default_factory=lambda: ["BR"])
    platform: str = Field("Hotmart/Kiwify", max_length=80)


class MinedAdPattern(BaseModel):
    source_ad_id: str = Field(..., min_length=2, max_length=120)
    active_ads: int = Field(0, ge=0)
    hook: str = Field(..., min_length=3, max_length=260)
    creative_pattern: str = Field(..., min_length=3, max_length=260)
    copy_pattern: str = Field(..., min_length=3, max_length=500)
    cta_pattern: str = Field("Comprar agora", max_length=120)
    connect_rate: float = Field(0, ge=0)
    roas: float = Field(0, ge=0)


class WarKitRequest(BaseModel):
    product: ProductDNAInput
    mined_ads: list[MinedAdPattern] = Field(default_factory=list, max_length=50)
    generate_pdf: bool = True
    generate_images: bool = True
    generate_videos: bool = True
    generate_copies: bool = True
    push_to_storage: bool = False
    prepare_meta_upload: bool = True
    dry_run_meta: bool = True
    render_video_assets: bool = False


class GeneratedFileItem(BaseModel):
    kind: str
    name: str
    relative_path: str
    absolute_path: str
    status: str = "created"


class WarKitResponse(BaseModel):
    product_name: str
    generated_at: datetime
    provider: str
    output_root: str
    kit_folder: str
    local_link: str
    total_files: int
    files: list[GeneratedFileItem]
    folder_structure: dict
    meta_ready: bool
    storage_status: str
    warnings: list[str]
