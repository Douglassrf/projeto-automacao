"""Domínio: kit de campanha gerado (War Kit)."""

from pydantic import BaseModel


class CampaignKitConfig(BaseModel):
    kit_output_dir: str = "/data/campaign_kits"
