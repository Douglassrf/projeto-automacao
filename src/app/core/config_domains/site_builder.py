"""Domínio: gerador de sites."""

from pydantic import BaseModel


class SiteBuilderConfig(BaseModel):
    site_output_dir: str = "/data/generated_sites"
