"""Domínio: diagnóstico automático (Missão 44)."""

from pydantic import BaseModel


class DiagnosticsConfig(BaseModel):
    diagnostics_disk_path: str = "."
    diagnostics_disk_warning_free_mb: int = 500
    diagnostics_disk_critical_free_mb: int = 100
