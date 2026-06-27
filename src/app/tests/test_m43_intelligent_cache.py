"""Missão 43 — Cache Inteligente.

Cobre: TTL (default e explicito, incluindo o sentinel "sem expiracao"),
miss/hit/expiracao via CacheService, evicao LRU por namespace ao exceder
cache_max_entries_per_namespace, estatisticas cumulativas por namespace
(hits/misses/sets/evictions/expired_purged), invalidate_namespace()/clear(),
purge_expired(), os novos endpoints /cache/* e as novas regras de
validate_settings()/CONFIG_SCHEMA_VERSION (Missão 43).
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.domain.models import CacheEntry
from app.main import app
from app.services.cache_service import CacheService

UTC = timezone.utc


def _ns() -> str:
    return f"m43-{uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# get/set basico + miss/hit
# ---------------------------------------------------------------------------


def test_get_on_missing_key_returns_none_and_counts_miss():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        assert service.get("nope", namespace=namespace) is None
        stats = service.stats(namespace=namespace)
        assert stats["per_namespace"][namespace]["misses"] == 1
        assert stats["per_namespace"][namespace]["hits"] == 0
    finally:
        db.close()


def test_set_then_get_returns_same_value_and_counts_hit():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("k1", {"a": 1, "b": [1, 2, 3]}, namespace=namespace)
        value = service.get("k1", namespace=namespace)
        assert value == {"a": 1, "b": [1, 2, 3]}
        stats = service.stats(namespace=namespace)
        assert stats["per_namespace"][namespace]["sets"] == 1
        assert stats["per_namespace"][namespace]["hits"] == 1
    finally:
        db.close()


def test_set_overwrites_existing_key_in_same_namespace():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("k1", "v1", namespace=namespace)
        service.set("k1", "v2", namespace=namespace)
        assert service.get("k1", namespace=namespace) == "v2"
        count = db.query(CacheEntry).filter(
            CacheEntry.namespace == namespace, CacheEntry.cache_key == "k1"
        ).count()
        assert count == 1
    finally:
        db.close()


def test_same_key_different_namespaces_are_independent():
    ns_a, ns_b = _ns(), _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("shared-key", "from-a", namespace=ns_a)
        service.set("shared-key", "from-b", namespace=ns_b)
        assert service.get("shared-key", namespace=ns_a) == "from-a"
        assert service.get("shared-key", namespace=ns_b) == "from-b"
    finally:
        db.close()


def test_get_value_none_is_a_hit_not_a_miss_get_entry_disambiguates():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("nullish", None, namespace=namespace)
        # get() retorna None tanto para "valor None armazenado" quanto para
        # miss - cada chamada e um hit real (lookup encontrou a linha viva),
        # entao duas chamadas (get + get_entry) somam 2 hits, nao 1.
        assert service.get("nullish", namespace=namespace) is None
        entry = service.get_entry("nullish", namespace=namespace)
        assert entry is not None
        stats = service.stats(namespace=namespace)
        assert stats["per_namespace"][namespace]["hits"] == 2
        assert stats["per_namespace"][namespace]["misses"] == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TTL: default, explicito, e sentinel "sem expiracao" (ttl_seconds<=0)
# ---------------------------------------------------------------------------


def test_set_without_ttl_uses_configured_default_ttl():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        before = datetime.now(UTC)
        entry = service.set("k", "v", namespace=namespace)
        expected_min = before + timedelta(seconds=service.settings.cache_default_ttl_seconds - 2)
        expected_max = before + timedelta(seconds=service.settings.cache_default_ttl_seconds + 2)
        assert entry.expires_at is not None
        got = entry.expires_at.replace(tzinfo=UTC) if entry.expires_at.tzinfo is None else entry.expires_at
        assert expected_min <= got <= expected_max
    finally:
        db.close()


def test_set_with_explicit_ttl_expires_and_is_purged_on_get():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("short", "v", namespace=namespace, ttl_seconds=5)
        entry = db.query(CacheEntry).filter(
            CacheEntry.namespace == namespace, CacheEntry.cache_key == "short"
        ).first()
        # simula a passagem do tempo diretamente na linha, sem violar o
        # contrato publico do service (nao ha "fast-forward" de relogio).
        entry.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

        assert service.get("short", namespace=namespace) is None
        remaining = db.query(CacheEntry).filter(
            CacheEntry.namespace == namespace, CacheEntry.cache_key == "short"
        ).count()
        assert remaining == 0
        stats = service.stats(namespace=namespace)
        assert stats["per_namespace"][namespace]["expired_purged"] == 1
        assert stats["per_namespace"][namespace]["misses"] == 1
    finally:
        db.close()


def test_ttl_seconds_zero_or_negative_means_never_expires():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        entry_zero = service.set("never-a", "v", namespace=namespace, ttl_seconds=0)
        entry_neg = service.set("never-b", "v", namespace=namespace, ttl_seconds=-1)
        assert entry_zero.expires_at is None
        assert entry_neg.expires_at is None
        assert service.get("never-a", namespace=namespace) == "v"
        assert service.get("never-b", namespace=namespace) == "v"
    finally:
        db.close()


def test_purge_expired_removes_dead_rows_without_a_get():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("a", "1", namespace=namespace)
        service.set("b", "2", namespace=namespace)
        for key in ("a", "b"):
            row = db.query(CacheEntry).filter(
                CacheEntry.namespace == namespace, CacheEntry.cache_key == key
            ).first()
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

        removed = service.purge_expired(namespace=namespace)
        assert removed == 2
        stats = service.stats(namespace=namespace)
        assert stats["per_namespace"][namespace]["expired_purged"] == 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Evicao LRU por namespace
# ---------------------------------------------------------------------------


def test_lru_eviction_triggers_when_namespace_exceeds_max_entries():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        original_max = service.settings.cache_max_entries_per_namespace
        service.settings.cache_max_entries_per_namespace = 3

        service.set("k1", "v1", namespace=namespace)
        service.set("k2", "v2", namespace=namespace)
        service.set("k3", "v3", namespace=namespace)
        service.get("k1", namespace=namespace)
        service.get("k2", namespace=namespace)

        service.set("k4", "v4", namespace=namespace)

        assert service.get("k3", namespace=namespace) is None
        assert service.get("k1", namespace=namespace) == "v1"
        assert service.get("k2", namespace=namespace) == "v2"
        assert service.get("k4", namespace=namespace) == "v4"

        count = db.query(CacheEntry).filter(CacheEntry.namespace == namespace).count()
        assert count == 3
        service.settings.cache_max_entries_per_namespace = original_max
    finally:
        db.close()


def test_lru_eviction_is_scoped_per_namespace_not_global():
    ns_a, ns_b = _ns(), _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        original_max = service.settings.cache_max_entries_per_namespace
        service.settings.cache_max_entries_per_namespace = 2

        service.set("a1", "1", namespace=ns_a)
        service.set("a2", "2", namespace=ns_a)
        service.set("b1", "1", namespace=ns_b)
        service.set("b2", "2", namespace=ns_b)
        assert service.get("a1", namespace=ns_a) == "1"
        assert service.get("b1", namespace=ns_b) == "1"
        stats_a = service.stats(namespace=ns_a)
        assert stats_a["per_namespace"][ns_a]["evictions"] == 0
        service.settings.cache_max_entries_per_namespace = original_max
    finally:
        db.close()


# ---------------------------------------------------------------------------
# delete / invalidate_namespace / clear
# ---------------------------------------------------------------------------


def test_delete_removes_key_and_returns_true_false_correctly():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("k", "v", namespace=namespace)
        assert service.delete("k", namespace=namespace) is True
        assert service.delete("k", namespace=namespace) is False
        assert service.get("k", namespace=namespace) is None
    finally:
        db.close()


def test_invalidate_namespace_removes_only_that_namespace():
    ns_a, ns_b = _ns(), _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("k", "v", namespace=ns_a)
        service.set("k", "v", namespace=ns_b)

        removed = service.invalidate_namespace(ns_a)
        assert removed == 1
        assert service.get("k", namespace=ns_a) is None
        assert service.get("k", namespace=ns_b) == "v"
    finally:
        db.close()


def test_clear_removes_every_namespace():
    ns_a, ns_b = _ns(), _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("k", "v", namespace=ns_a)
        service.set("k", "v", namespace=ns_b)
        service.clear()
        assert service.get("k", namespace=ns_a) is None
        assert service.get("k", namespace=ns_b) is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# stats(): agregacao global vs por namespace
# ---------------------------------------------------------------------------


def test_stats_without_namespace_aggregates_across_namespaces():
    ns_a, ns_b = _ns(), _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        service.set("k", "v", namespace=ns_a)
        service.get("k", namespace=ns_a)
        service.set("k", "v", namespace=ns_b)
        service.get("missing", namespace=ns_b)

        global_stats = service.stats()
        assert global_stats["sets"] >= 2
        assert global_stats["hits"] >= 1
        assert global_stats["misses"] >= 1
        assert ns_a in global_stats["per_namespace"]
        assert ns_b in global_stats["per_namespace"]
        assert 0.0 <= global_stats["hit_rate"] <= 1.0
    finally:
        db.close()


def test_stats_hit_rate_is_zero_when_no_requests_yet():
    namespace = _ns()
    db = SessionLocal()
    try:
        service = CacheService(db)
        stats = service.stats(namespace=namespace)
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
    finally:
        db.close()


def test_stats_backend_field_reflects_configured_backend():
    db = SessionLocal()
    try:
        service = CacheService(db)
        stats = service.stats()
        assert stats["backend"] == service.settings.cache_backend
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API: /cache/entries, /cache/stats, /cache/invalidate, /cache/clear,
# /cache/purge-expired
# ---------------------------------------------------------------------------


def test_set_entry_endpoint_then_get_entry_endpoint():
    namespace = _ns()
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/cache/entries",
            json={"key": "k1", "value": {"x": 1}, "namespace": namespace},
        )
        assert created.status_code == 200
        body = created.json()
        assert body["key"] == "k1"
        assert body["namespace"] == namespace
        assert body["value"] == {"x": 1}

        fetched = client.get("/api/v1/cache/entries/k1", params={"namespace": namespace})
        assert fetched.status_code == 200
        assert fetched.json()["value"] == {"x": 1}


def test_get_entry_endpoint_returns_404_on_miss():
    namespace = _ns()
    with TestClient(app) as client:
        response = client.get("/api/v1/cache/entries/does-not-exist", params={"namespace": namespace})
        assert response.status_code == 404


def test_delete_entry_endpoint():
    namespace = _ns()
    with TestClient(app) as client:
        client.post(
            "/api/v1/cache/entries", json={"key": "k1", "value": "v", "namespace": namespace}
        )
        response = client.post(
            "/api/v1/cache/entries/k1/delete", params={"namespace": namespace}
        )
        assert response.status_code == 200
        assert response.json()["deleted"] is True


def test_invalidate_endpoint_via_api():
    namespace = _ns()
    with TestClient(app) as client:
        client.post(
            "/api/v1/cache/entries", json={"key": "k1", "value": "v", "namespace": namespace}
        )
        client.post(
            "/api/v1/cache/entries", json={"key": "k2", "value": "v", "namespace": namespace}
        )
        response = client.post("/api/v1/cache/invalidate", json={"namespace": namespace})
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 2


def test_clear_endpoint_via_api():
    namespace = _ns()
    with TestClient(app) as client:
        client.post(
            "/api/v1/cache/entries", json={"key": "k1", "value": "v", "namespace": namespace}
        )
        response = client.post("/api/v1/cache/clear")
        assert response.status_code == 200
        assert response.json()["deleted_count"] >= 1


def test_purge_expired_endpoint_via_api():
    namespace = _ns()
    with TestClient(app) as client:
        client.post(
            "/api/v1/cache/entries",
            json={"key": "k1", "value": "v", "namespace": namespace},
        )
        db = SessionLocal()
        try:
            row = db.query(CacheEntry).filter(
                CacheEntry.namespace == namespace, CacheEntry.cache_key == "k1"
            ).first()
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()

        response = client.post("/api/v1/cache/purge-expired", params={"namespace": namespace})
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 1


def test_stats_endpoint_returns_expected_shape():
    namespace = _ns()
    with TestClient(app) as client:
        client.post(
            "/api/v1/cache/entries", json={"key": "k1", "value": "v", "namespace": namespace}
        )
        response = client.get("/api/v1/cache/stats", params={"namespace": namespace})
        assert response.status_code == 200
        data = response.json()
        for key in ("backend", "hits", "misses", "sets", "evictions", "expired_purged", "hit_rate", "size", "live_size", "per_namespace"):
            assert key in data
        assert namespace in data["per_namespace"]


# ---------------------------------------------------------------------------
# Config: schema version + novas regras de validacao (Missao 43)
# ---------------------------------------------------------------------------


def test_config_schema_version_bumped_for_mission_43():
    # >= em vez de == (ver comentario equivalente em test_m42_intelligent_queue.py)
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (1, 2, 0)


def test_validate_settings_rejects_cache_default_ttl_below_one():
    settings = get_settings()
    previous = settings.cache_default_ttl_seconds
    try:
        settings.cache_default_ttl_seconds = 0
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("cache_default_ttl_seconds" in issue for issue in issues)
    finally:
        settings.cache_default_ttl_seconds = previous


def test_validate_settings_rejects_cache_max_entries_below_one():
    settings = get_settings()
    previous = settings.cache_max_entries_per_namespace
    try:
        settings.cache_max_entries_per_namespace = 0
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("cache_max_entries_per_namespace" in issue for issue in issues)
    finally:
        settings.cache_max_entries_per_namespace = previous


def test_validate_settings_accepts_default_cache_config():
    settings = get_settings()
    issues = validate_settings(settings, Environment.DEVELOPMENT)
    assert not any("cache_" in issue for issue in issues)
