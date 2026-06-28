"""Domínio: Architecture Evolution Report (Missão 79)."""

from pydantic import BaseModel


class ArchitectureEvolutionConfig(BaseModel):
    # Missao 79 - Architecture Evolution Report
    architecture_evolution_include_recommendations: bool = True
