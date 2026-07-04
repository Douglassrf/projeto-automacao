"""Domínio: integração Deriv API."""

from pydantic import BaseModel


class DerivConfig(BaseModel):
    deriv_app_id: str = "1089"
    deriv_endpoint: str = "ws.derivws.com"
    deriv_api_token: str | None = None
    deriv_default_symbol: str = "R_100"
    deriv_default_currency: str = "USD"
    deriv_mock_enabled: bool = True
    deriv_timeout_seconds: float = 10.0
