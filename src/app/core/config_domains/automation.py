"""Domínio: níveis de automação e loop de aprendizado."""

from pydantic import BaseModel


class AutomationConfig(BaseModel):
    learning_loop_enabled: bool = True
    automation_level: int = 0
    automation_level_2_enabled: bool = False
    automation_daily_spend_limit_brl: float = 50.0
    kill_switch_enabled: bool = False
