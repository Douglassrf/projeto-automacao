"""Domínio: moeda, câmbio e orçamento de campanha."""

from pydantic import BaseModel


class CurrencyConfig(BaseModel):
    currency_code: str = "BRL"
    currency_ad_account: str = "BRL"
    currency_sales: str = "EUR"
    exchange_rate_usd_to_brl: float = 5.0
    exchange_rate_eur_to_brl: float = 5.5
    test_budget_brl: float = 25.0
    scale_budget_brl: float = 50.0
    scale_min_ctr: float = 1.5
    scale_min_roas: float = 1.0
