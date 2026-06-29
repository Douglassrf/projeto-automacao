"""Domínio: Production Launch Authorization (Missão 91)."""

from pydantic import BaseModel


class ProductionLaunchAuthorizationConfig(BaseModel):
    production_launch_fail_closed: bool = True
    production_launch_require_evidence_archive: bool = True
