"""Domínio: testes de recuperação (Missão 47)."""

from pydantic import BaseModel


class RecoveryConfig(BaseModel):
    recovery_max_jobs_per_sweep: int = 100
