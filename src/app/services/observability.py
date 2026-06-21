from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

import sentry_sdk

from app.core.config import get_settings
from app.core.immutable_audit import ImmutableAuditLog

_LOGGER = logging.getLogger("adintelligence.observability")
_INITIALIZED = False
_METRICS: dict[str, dict[str, float]] = defaultdict(
    lambda: {"count": 0, "errors": 0, "total_latency_ms": 0.0, "max_latency_ms": 0.0}
)


def init_observability() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
    _INITIALIZED = True


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _logs_dir() -> Path:
    path = _project_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log_file() -> Path:
    return _logs_dir() / "observability_events.log"


def _audit_file() -> Path:
    return _logs_dir() / "audit_events.log"


def _immutable_audit_file() -> Path:
    return _logs_dir() / "immutable_audit_events.log"


def new_trace_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def trace_context(
    *,
    correlation_id: str | None = None,
    execution_id: str | None = None,
    mission_id: str | int | None = None,
) -> dict[str, str]:
    return {
        "correlation_id": correlation_id or new_trace_id("corr"),
        "execution_id": execution_id or new_trace_id("exec"),
        "mission_id": str(mission_id or "mission_27"),
    }


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, limit: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()[-limit:]
    for line in lines:
        try:
            payload = json.loads(line.strip())
            if isinstance(payload, dict):
                records.append(payload)
        except json.JSONDecodeError:
            continue
    return records


def log_event(
    event_type: str,
    *,
    status: str = "ok",
    latency_ms: float | None = None,
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    execution_id: str | None = None,
    mission_id: str | int | None = None,
) -> dict[str, Any]:
    init_observability()
    context = trace_context(
        correlation_id=correlation_id,
        execution_id=execution_id,
        mission_id=mission_id,
    )
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "status": status,
        "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
        **context,
        "details": details or {},
    }
    _LOGGER.info("observability_event %s", json.dumps(record, ensure_ascii=False))
    try:
        _append_jsonl(_log_file(), record)
    except Exception:
        pass
    return record


def audit_event(
    *,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    status: str = "ok",
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    execution_id: str | None = None,
    mission_id: str | int | None = None,
) -> dict[str, Any]:
    context = trace_context(
        correlation_id=correlation_id,
        execution_id=execution_id,
        mission_id=mission_id,
    )
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "actor": actor,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "status": status,
        **context,
        "details": details or {},
    }
    try:
        _append_jsonl(_audit_file(), record)
    except Exception:
        pass
    log_event(
        "audit_event",
        status=status,
        details={
            "actor": actor,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
        },
        **context,
    )
    return record


def immutable_audit_event(
    *,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    status: str = "ok",
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    execution_id: str | None = None,
    mission_id: str | int | None = None,
) -> dict[str, Any]:
    record = audit_event(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        details=details,
        correlation_id=correlation_id,
        execution_id=execution_id,
        mission_id=mission_id,
    )
    return ImmutableAuditLog(_immutable_audit_file()).append(record)


def immutable_audit_health() -> dict[str, Any]:
    audit_log = ImmutableAuditLog(_immutable_audit_file())
    verification = audit_log.verify()
    return {
        "immutable_audit_file": str(_immutable_audit_file()),
        "immutable_audit_file_exists": _immutable_audit_file().exists(),
        "hash_chain_ok": verification.ok,
        "total_events": verification.total_events,
        "broken_at": verification.broken_at,
        "reason": verification.reason,
    }


@contextmanager
def timed_event(
    event_type: str,
    details: dict[str, Any] | None = None,
    *,
    correlation_id: str | None = None,
    execution_id: str | None = None,
    mission_id: str | int | None = None,
) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000
        log_event(
            event_type,
            status="error",
            latency_ms=latency,
            details={**(details or {}), "error": str(exc)},
            correlation_id=correlation_id,
            execution_id=execution_id,
            mission_id=mission_id,
        )
        sentry_sdk.capture_exception(exc)
        raise
    else:
        latency = (time.perf_counter() - start) * 1000
        log_event(
            event_type,
            status="ok",
            latency_ms=latency,
            details=details or {},
            correlation_id=correlation_id,
            execution_id=execution_id,
            mission_id=mission_id,
        )


def observability_health() -> dict[str, Any]:
    settings = get_settings()
    observability_log = _log_file()
    audit_log = _audit_file()
    return {
        "enabled": settings.observability_enabled,
        "sentry_configured": bool(settings.sentry_dsn),
        "log_file": str(observability_log),
        "audit_file": str(audit_log),
        "immutable_audit_file": str(_immutable_audit_file()),
        "log_file_exists": observability_log.exists(),
        "audit_file_exists": audit_log.exists(),
        "immutable_audit_supported": True,
        "mission_id_supported": True,
        "correlation_id_supported": True,
        "execution_id_supported": True,
        "monitored_signals": [
            "meta_api_latency",
            "render_error_rate",
            "queue_latency",
            "premium_render_postprocessing",
            "agent_route_health",
            "audit_events",
        ],
    }


def health_dashboard(limit: int = 10) -> dict[str, Any]:
    try:
        from app.api.safe_router import FAILED_ROUTES, LOADED_ROUTES
    except Exception:
        FAILED_ROUTES = []
        LOADED_ROUTES = []

    recent_events = _read_jsonl(_log_file(), limit)
    recent_audit = _read_jsonl(_audit_file(), limit)
    error_events = [event for event in recent_events if event.get("status") != "ok"]
    return {
        "status": "ok" if not FAILED_ROUTES else "attention",
        "agent": "ObservabilityAgent",
        "audit_agent": "AuditLoggerAgent",
        "mission_id": "mission_27",
        "loaded_routes": len(LOADED_ROUTES),
        "failed_routes": len(FAILED_ROUTES),
        "failed_route_details": FAILED_ROUTES,
        "recent_events": recent_events,
        "recent_audit_events": recent_audit,
        "recent_error_events": error_events,
        "memory_guard": {
            "writes_project_logs": True,
            "uses_correlation_id": True,
            "uses_execution_id": True,
            "uses_mission_id": True,
        },
    }


def record_http_metric(*, method: str, path: str, status_code: int, latency_ms: float) -> None:
    route_key = f"{method.upper()} {path}"
    bucket = _METRICS[route_key]
    bucket["count"] += 1
    if status_code >= 500:
        bucket["errors"] += 1
    bucket["total_latency_ms"] += latency_ms
    bucket["max_latency_ms"] = max(bucket["max_latency_ms"], latency_ms)


def metrics_snapshot() -> dict[str, Any]:
    routes: dict[str, dict[str, float]] = {}
    total_requests = 0
    total_errors = 0
    for route, values in sorted(_METRICS.items()):
        count = int(values["count"])
        total_requests += count
        total_errors += int(values["errors"])
        avg_latency = values["total_latency_ms"] / count if count else 0.0
        routes[route] = {
            "requests_total": count,
            "errors_total": int(values["errors"]),
            "latency_avg_ms": round(avg_latency, 2),
            "latency_max_ms": round(values["max_latency_ms"], 2),
        }
    return {
        "format": "json",
        "requests_total": total_requests,
        "errors_total": total_errors,
        "routes": routes,
    }


def reset_metrics() -> None:
    _METRICS.clear()


def component_health_snapshot(engine_override: Any | None = None) -> dict[str, Any]:
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    from app.db.session import SessionLocal, engine
    from app.services.queue_service import QueueService

    components: dict[str, Any] = {}
    try:
        database_engine = engine_override or engine
        with database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        components["database"] = {"status": "ok"}
    except SQLAlchemyError as exc:
        components["database"] = {"status": "unavailable", "detail": type(exc).__name__}

    db = SessionLocal()
    try:
        components["queue"] = {"status": "ok", **QueueService(db).stats()}
    except Exception as exc:
        components["queue"] = {"status": "unavailable", "detail": type(exc).__name__}
    finally:
        db.close()

    audit = immutable_audit_health()
    components["audit"] = {
        "status": "ok" if audit.get("hash_chain_ok") else "unavailable",
        "hash_chain_ok": audit.get("hash_chain_ok"),
        "total_events": audit.get("total_events"),
        "reason": audit.get("reason"),
    }
    status = "ready" if all(item.get("status") == "ok" for item in components.values()) else "degraded"
    return {"status": status, "components": components, "dashboard": health_dashboard(limit=5)}


def operational_dashboard_snapshot() -> dict[str, Any]:
    return component_health_snapshot()
