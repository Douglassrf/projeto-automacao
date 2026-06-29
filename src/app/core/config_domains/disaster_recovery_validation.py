"""Domínio: Disaster Recovery Validation (Missão 88)."""

from pydantic import BaseModel


class DisasterRecoveryValidationConfig(BaseModel):
    disaster_recovery_simulate_db_down: bool = True
    disaster_recovery_validate_backup: bool = True
