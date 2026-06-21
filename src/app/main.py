import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine

from app.api.router import api_router
from app.core.api_gateway import api_gateway_guard
from app.core.config import get_settings
from app.services.observability import log_event, trace_context


app = FastAPI(title="Projeto Automacao - Runtime Seguro", version="1.0.0-final")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Correlation-ID",
        "X-Execution-ID",
        "X-Mission-ID",
        "X-Actor",
        "X-User-ID",
    ],
)


def _retry_after_seconds(reset_at: str) -> str:
    try:
        reset_time = datetime.fromisoformat(reset_at)
    except ValueError:
        return "60"
    now = datetime.now(timezone.utc)
    return str(max(1, int((reset_time - now).total_seconds())))


@app.middleware("http")
async def observability_trace_middleware(request: Request, call_next):
    context = trace_context(
        correlation_id=request.headers.get("x-correlation-id"),
        execution_id=request.headers.get("x-execution-id"),
        mission_id=request.headers.get("x-mission-id"),
    )
    start = time.perf_counter()
    gateway_decision = None if api_gateway_guard.should_bypass(request) else api_gateway_guard.evaluate(request)
    if gateway_decision is not None and not gateway_decision.allowed:
        latency_ms = (time.perf_counter() - start) * 1000
        log_event(
            "http_request",
            status="blocked",
            latency_ms=latency_ms,
            details={
                "method": request.method,
                "path": request.url.path,
                "status_code": 429,
                "gateway_rule": gateway_decision.rule,
                "gateway_reason": gateway_decision.rate_limit.reason,
            },
            **context,
        )
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit excedido.",
                "rule": gateway_decision.rule,
                "reset_at": gateway_decision.rate_limit.reset_at,
            },
            headers={
                "x-correlation-id": context["correlation_id"],
                "x-execution-id": context["execution_id"],
                "x-mission-id": context["mission_id"],
                "x-rate-limit-rule": gateway_decision.rule,
                "x-rate-limit-remaining": str(gateway_decision.rate_limit.remaining),
                "Retry-After": _retry_after_seconds(gateway_decision.rate_limit.reset_at),
            },
        )
    try:
        response = await call_next(request)
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        log_event(
            "http_request",
            status="error",
            latency_ms=latency_ms,
            details={"method": request.method, "path": request.url.path, "error": str(exc)},
            **context,
        )
        raise
    latency_ms = (time.perf_counter() - start) * 1000
    log_event(
        "http_request",
        status="ok" if response.status_code < 500 else "error",
        latency_ms=latency_ms,
        details={"method": request.method, "path": request.url.path, "status_code": response.status_code},
        **context,
    )
    response.headers["x-correlation-id"] = context["correlation_id"]
    response.headers["x-execution-id"] = context["execution_id"]
    response.headers["x-mission-id"] = context["mission_id"]
    response.headers["x-rate-limit-rule"] = gateway_decision.rule if gateway_decision is not None else "bypassed"
    response.headers["x-rate-limit-remaining"] = (
        str(gateway_decision.rate_limit.remaining) if gateway_decision is not None else "not-applied"
    )
    return response


@app.get("/")
def root():
    return {"status": "ok", "message": "API rodando", "mode": "safe-runtime"}


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "status": "unhealthy",
                "database": "unavailable",
                "detail": type(exc).__name__,
            },
        )
    return {"ok": True, "status": "healthy", "database": "ok", "motor": "ligado"}


@app.get("/diagnostics")
def diagnostics():
    return {
        "ok": True,
        "motor": "ligado",
        "agents_mode": "isolado",
        "note": "Runtime principal protegido; agentes reconectados via safe_router."
    }


app.include_router(api_router)
