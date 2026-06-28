from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CacheSetRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    value: Any
    namespace: str = Field(default="default", min_length=1, max_length=80)
    ttl_seconds: int | None = None


class CacheEntryResponse(BaseModel):
    id: int
    namespace: str
    key: str
    value: Any
    hits: int
    expires_at: datetime | None
    created_at: datetime
    last_accessed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CacheDeleteResponse(BaseModel):
    deleted: bool


class CacheInvalidateRequest(BaseModel):
    namespace: str = Field(..., min_length=1, max_length=80)


class CacheInvalidateResponse(BaseModel):
    deleted_count: int


class CacheNamespaceStats(BaseModel):
    hits: int
    misses: int
    sets: int
    evictions: int
    expired_purged: int
    size: int


class CacheStatsResponse(BaseModel):
    backend: str
    hits: int
    misses: int
    sets: int
    evictions: int
    expired_purged: int
    hit_rate: float
    size: int
    live_size: int
    per_namespace: dict[str, CacheNamespaceStats]
