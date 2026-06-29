"""Domínio: Continuous Quality Gate (Missão 74)."""

from pydantic import BaseModel


class ContinuousQualityConfig(BaseModel):
    # Missao 74 - Continuous Quality Gate: quando True (padrao), padroes de
    # codigo sao verificados e falhas bloqueiam o gate. Nunca False em prod.
    quality_gate_enforce_standards: bool = True
