from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.domain.models import User
from app.services.load_test_mission27a import run_mission27a_load_test
from app.services.observability import audit_event, health_dashboard, observability_health, trace_context

router = APIRouter(prefix="/observability", tags=["Observability"])


@router.get("/health")
def get_observability_health(current_user: User = Depends(get_current_user)):
    return observability_health()


@router.get("/dashboard")
def get_observability_dashboard(current_user: User = Depends(get_current_user)):
    return health_dashboard()


@router.post("/audit")
def create_audit_event(payload: dict, current_user: User = Depends(get_current_user)):
    context = trace_context(
        correlation_id=payload.get("correlation_id"),
        execution_id=payload.get("execution_id"),
        mission_id=payload.get("mission_id"),
    )
    return audit_event(
        actor=payload.get("actor") or getattr(current_user, "email", "system"),
        action=str(payload.get("action") or "unspecified"),
        resource_type=str(payload.get("resource_type") or "runtime"),
        resource_id=payload.get("resource_id"),
        status=str(payload.get("status") or "ok"),
        details=payload.get("details") if isinstance(payload.get("details"), dict) else {},
        **context,
    )


@router.post("/load-test/mission-27a")
def run_controlled_load_test(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    payload = payload or {}
    batches = tuple(int(item) for item in payload.get("batches", [10, 50, 100]))
    concurrency = int(payload.get("concurrency", 8))
    persist = bool(payload.get("persist", True))
    return run_mission27a_load_test(batches=batches, concurrency=concurrency, persist=persist)
