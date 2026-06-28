"""Domínio: rede de afiliados."""

from pydantic import BaseModel


class AffiliateConfig(BaseModel):
    affiliate_network: str = "generic"
    affiliate_api_key: str | None = None
    affiliate_api_secret: str | None = None
    affiliate_default_id: str | None = "demo-affiliate"
    affiliate_mock_enabled: bool = True
