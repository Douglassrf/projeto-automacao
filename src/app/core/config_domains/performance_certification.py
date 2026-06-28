"""Domínio: Performance Certification (Missão 87)."""

from pydantic import BaseModel


class PerformanceCertificationConfig(BaseModel):
    performance_cert_max_latency_ms: int = 500
    performance_cert_enable_stress: bool = True
