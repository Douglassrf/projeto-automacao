from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


EventName = Literal["Purchase", "Lead", "AddToCart", "InitiateCheckout", "ViewContent", "PageView"]


class CustomerDataInput(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    zip_code: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    external_id: str | None = Field(default=None, max_length=180)
    client_ip_address: str | None = Field(default=None, max_length=80)
    client_user_agent: str | None = Field(default=None, max_length=500)
    fbp: str | None = Field(default=None, max_length=250)
    fbc: str | None = Field(default=None, max_length=250)

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.lower().strip() if value else value


class CapiEnterpriseEvent(BaseModel):
    event_name: EventName
    event_id: str | None = Field(default=None, max_length=160)
    event_time: datetime | None = None
    event_source_url: HttpUrl | None = None
    action_source: Literal["website", "app", "phone_call", "chat", "email", "system_generated", "business_messaging", "physical_store"] = "website"
    pixel_id: str | None = Field(default=None, max_length=80)
    value: float = Field(default=0, ge=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    order_id: str | None = Field(default=None, max_length=160)
    product_name: str | None = Field(default=None, max_length=180)
    campaign_id: str | None = Field(default=None, max_length=120)
    ad_id: str | None = Field(default=None, max_length=120)
    customer: CustomerDataInput = Field(default_factory=CustomerDataInput)
    custom_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper().strip()


class CapiEnterpriseRequest(BaseModel):
    events: list[CapiEnterpriseEvent] = Field(..., min_length=1, max_length=100)
    forward_to_meta: bool = False
    dry_run: bool | None = None
    test_event_code: str | None = Field(default=None, max_length=120)


class CapiPreparedEvent(BaseModel):
    event_id: str
    event_name: str
    event_time: int
    action_source: str
    user_data: dict[str, Any]
    custom_data: dict[str, Any]
    event_source_url: str | None = None


class CapiEnterpriseEventResult(BaseModel):
    event_id: str
    event_name: str
    status: Literal["stored", "deduplicated", "forwarded", "blocked", "error"]
    forwarded_to_meta: bool
    deduplicated: bool
    event_match_quality_score: int
    warnings: list[str]
    meta_response: dict[str, Any] | None = None


class CapiEnterpriseResponse(BaseModel):
    status: Literal["ok", "partial", "error"]
    received: int
    stored: int
    forwarded: int
    deduplicated: int
    dry_run: bool
    results: list[CapiEnterpriseEventResult]
    log_file: str


class CapiHealthResponse(BaseModel):
    capi_enabled: bool
    dry_run: bool
    pixel_configured: bool
    token_configured: bool
    test_event_code_configured: bool
    production_ready: bool
    recommendations: list[str]


class CapiBrowserPixelPayloadRequest(BaseModel):
    event: CapiEnterpriseEvent


class CapiBrowserPixelPayloadResponse(BaseModel):
    event_id: str
    browser_payload: dict[str, Any]
    note: str

    model_config = ConfigDict(json_schema_extra={"description": "Payload para enviar também no Pixel browser-side usando o mesmo event_id da CAPI."})
