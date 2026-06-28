"""Domínio: sistema de alertas (Missão 46)."""

from pydantic import BaseModel


class AlertsConfig(BaseModel):
    alert_history_default_limit: int = 50
