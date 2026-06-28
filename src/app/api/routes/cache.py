from fastapi import APIRouter, HTTPException, Query, Depends

from app.core.container import get_cache_service
from app.schemas.cache import (
    CacheDeleteResponse,
    CacheEntryResponse,
    CacheInvalidateRequest,
    CacheInvalidateResponse,
    CacheSetRequest,
    CacheStatsResponse,
)
from app.services.cache_service import CacheService, serialize_entry

router = APIRouter(prefix="/cache", tags=["Cache Inteligente"])


@router.post("/entries", response_model=CacheEntryResponse)
def set_entry(payload: CacheSetRequest, cache: CacheService = Depends(get_cache_service)):
    entry = cache.set(
        payload.key,
        payload.value,
        namespace=payload.namespace,
        ttl_seconds=payload.ttl_seconds,
    )
    return serialize_entry(entry)


@router.get("/entries/{key}", response_model=CacheEntryResponse)
def get_entry(key: str, namespace: str = Query(default="default"), cache: CacheService = Depends(get_cache_service)):
    entry = cache.get_entry(key, namespace=namespace)
    if entry is None:
        raise HTTPException(status_code=404, detail="cache miss")
    return serialize_entry(entry)


@router.post("/entries/{key}/delete", response_model=CacheDeleteResponse)
def delete_entry(
    key: str, namespace: str = Query(default="default"), cache: CacheService = Depends(get_cache_service)
):
    deleted = cache.delete(key, namespace=namespace)
    return {"deleted": deleted}


@router.post("/invalidate", response_model=CacheInvalidateResponse)
def invalidate_namespace(payload: CacheInvalidateRequest, cache: CacheService = Depends(get_cache_service)):
    count = cache.invalidate_namespace(payload.namespace)
    return {"deleted_count": count}


@router.post("/clear", response_model=CacheInvalidateResponse)
def clear_cache(cache: CacheService = Depends(get_cache_service)):
    count = cache.clear()
    return {"deleted_count": count}


@router.post("/purge-expired", response_model=CacheInvalidateResponse)
def purge_expired(namespace: str | None = Query(default=None), cache: CacheService = Depends(get_cache_service)):
    count = cache.purge_expired(namespace=namespace)
    return {"deleted_count": count}


@router.get("/stats", response_model=CacheStatsResponse)
def cache_stats(namespace: str | None = Query(default=None), cache: CacheService = Depends(get_cache_service)):
    return cache.stats(namespace=namespace)
