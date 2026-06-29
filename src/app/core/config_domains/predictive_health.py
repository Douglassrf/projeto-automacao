"""Domínio: Predictive Health Monitor (Missão 72)."""

from pydantic import BaseModel


class PredictiveHealthConfig(BaseModel):
    # Missao 72 - Predictive Health Monitor: quando True (padrao), alertas
    # preditivos baseados em tendencias de CPU/memoria/armazenamento sao
    # incluidos no relatorio. Nunca deve ser False em producao — ocultar
    # alertas preditivos nao elimina degradacao gradual.
    predictive_health_enable_predictive_alerts: bool = True
    predictive_health_history_max_snapshots: int = 24
