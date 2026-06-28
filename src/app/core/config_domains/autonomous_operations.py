"""Domínio: Autonomous Operations Readiness (Missão 80)."""

from pydantic import BaseModel


class AutonomousOperationsConfig(BaseModel):
    # Missao 80 - Autonomous Operations Readiness (CAPSTONE): gate fail-closed.
    # Quando True (padrao), verdict so e READY se todos os dominios passarem.
    # Quando False, verdict e sempre NOT_READY. Nunca False em producao.
    autonomous_ops_require_all_domains: bool = True
