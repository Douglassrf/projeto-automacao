"""Domínio: fila de jobs (Missão 42 — Gerenciador Inteligente de Filas)."""

from pydantic import BaseModel


class QueueConfig(BaseModel):
    queue_backend: str = "sqlite"
    queue_sqlite_wal_enabled: bool = True
    queue_default_max_attempts: int = 3
    queue_lock_timeout_seconds: int = 900
    keydb_url: str | None = None
    # Missao 42 - Gerenciador Inteligente de Filas.
    queue_retry_backoff_base_seconds: int = 5
    queue_retry_backoff_max_seconds: int = 300
    queue_starvation_threshold_seconds: int = 600
    queue_failure_rate_threshold: float = 0.5
