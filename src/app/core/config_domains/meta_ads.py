"""Domínio: Meta Ads / Conversions API (CAPI)."""

from pydantic import BaseModel


class MetaAdsConfig(BaseModel):
    meta_access_token: str | None = None
    meta_ad_account_id: str | None = None
    meta_page_id: str | None = None
    meta_instagram_actor_id: str | None = None
    meta_pixel_id: str | None = None
    capi_pixel_id: str | None = None
    meta_api_version: str = "v20.0"
    meta_env: str = "sandbox"
    meta_dry_run: bool = True
    meta_allow_active_launch: bool = False
    meta_operator_enabled: bool = True
    meta_autopublish: bool = False
    meta_allow_production_real: bool = False
    meta_production_daily_spend_limit_brl: float = 50.0
    meta_require_manual_confirmation: bool = True
    meta_created_resources_log: str = "/data/runtime/meta_created_resources.jsonl"
    capi_enabled: bool = False
    capi_test_event_code: str | None = None
