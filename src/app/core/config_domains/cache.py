"""Domínio: cache (Missão 43 — Cache Inteligente)."""

from pydantic import BaseModel


class CacheConfig(BaseModel):
    cache_default_ttl_seconds: int = 300
    cache_max_entries_per_namespace: int = 1000
    cache_backend: str = "sqlite"
