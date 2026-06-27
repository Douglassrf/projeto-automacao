from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.enterprise_certification import omega_enterprise_report

router = APIRouter(prefix="/enterprise-certification", tags=["enterprise-certification"])


class DouglasGoldRequest(BaseModel):
    gates: dict[str, bool] = Field(default_factory=dict)


@router.get("/omega-report")
def get_omega_enterprise_report() -> dict[str, Any]:
    return omega_enterprise_report()


@router.post("/douglas-gold")
def post_douglas_gold_certification(payload: DouglasGoldRequest) -> dict[str, Any]:
    return omega_enterprise_report(payload.gates)["missions"]["omega20"]
