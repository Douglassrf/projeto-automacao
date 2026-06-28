"""Domínio: Pre Production Approval (Missão 90)."""

from pydantic import BaseModel


class PreProductionApprovalConfig(BaseModel):
    pre_production_require_all_missions: bool = True
    pre_production_block_on_issues: bool = True
