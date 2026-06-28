"""Domínio: Data Integrity Framework (Missão 75)."""

from pydantic import BaseModel


class DataIntegrityConfig(BaseModel):
    # Missao 75 - Data Integrity Framework: validacao estrita de registros.
    data_integrity_strict_validation: bool = True
