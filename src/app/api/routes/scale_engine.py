"""Rotas V4/V5/V6 — escala com protecao da fase de aprendizado da Meta."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import scale_engine

router = APIRouter(prefix="/scale", tags=["Escala V4-V6"])


class ScaleRequest(BaseModel):
    current_budget_brl: float | None = Field(None, description="Orcamento diario atual")
    current_countries: list[str] | None = None
    metrics: dict = Field(
        default_factory=dict,
        description=(
            "Metricas reais do gerenciador: conversions_last_7d, roas, cpa, target_cpa, "
            "frequency, hours_since_last_change, connect_rate, checkout_rate, "
            "purchase_rate, ctr_change_pct"
        ),
    )


@router.get("/status")
def status():
    return {
        "status": "ok",
        "stages": {
            "V4": "escala controlada (max +20%/24h, sem editar o conjunto)",
            "V5": "otimizacao inteligente (gargalo do funil + fadiga criativa)",
            "V6": "dominacao (expansao geo com criativos vencedores)",
        },
        "delivery_protection": {
            "max_budget_increase_pct": scale_engine.MAX_BUDGET_INCREASE_PCT,
            "min_hours_between_changes": scale_engine.MIN_HOURS_BETWEEN_CHANGES,
            "learning_phase_conversions": scale_engine.LEARNING_PHASE_CONVERSIONS,
            "roas_floor": scale_engine.ROAS_FLOOR_SCALE,
        },
    }


@router.post("/v4")
def v4(payload: ScaleRequest):
    return scale_engine.v4_scale_plan(payload.model_dump())


@router.post("/v5")
def v5(payload: ScaleRequest):
    return scale_engine.v5_optimize_plan(payload.model_dump())


@router.post("/v6")
def v6(payload: ScaleRequest):
    return scale_engine.v6_dominate_plan(payload.model_dump())
