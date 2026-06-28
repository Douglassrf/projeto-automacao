"""Domínio: Operational Intelligence Hub (Missão 71)."""

from pydantic import BaseModel


class OperationalIntelligenceConfig(BaseModel):
    # Missao 71 - Operational Intelligence Hub: quando True (padrao),
    # dependencias sem versao fixa (==) em requirements.txt aparecem nos
    # indicadores de risco do painel /operational-intelligence/* (alem de
    # afetar o overall_status como "degraded"). Nunca deve ser False em
    # producao - ocultar risco conhecido nao o elimina.
    operational_intelligence_include_unpinned_in_risk: bool = True
