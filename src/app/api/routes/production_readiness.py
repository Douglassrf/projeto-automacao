from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.production_readiness import (
    backup_sqlite,
    disaster_recovery_drill,
    enterprise_observability_snapshot,
    environment_profile,
    gold_certification_snapshot,
    liveness_probe,
    performance_max_plan,
    readiness_probe,
    restore_sqlite,
    security_enterprise_snapshot,
    shutdown_coordinator,
)
from app.domain.models import User

router = APIRouter(prefix="/production", tags=["Production Readiness"])


@router.get("/liveness")
def liveness():
    return liveness_probe()


@router.get("/readiness")
def readiness():
    probe = readiness_probe()
    if not probe["ok"]:
        return JSONResponse(status_code=503, content=probe)
    return probe


@router.get("/environment")
def environment(current_user: User = Depends(get_current_user)):
    return environment_profile()


@router.post("/shutdown")
def graceful_shutdown(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return shutdown_coordinator.request_shutdown(reason=(payload or {}).get("reason", "api"))


@router.post("/restart")
def graceful_restart(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return shutdown_coordinator.request_restart(reason=(payload or {}).get("reason", "api"))


@router.post("/backup")
def backup(current_user: User = Depends(get_current_user)):
    try:
        return backup_sqlite()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/restore")
def restore(payload: dict, current_user: User = Depends(get_current_user)):
    return restore_sqlite(Path(payload["backup_file"]), Path(payload["destination"]))


@router.get("/observability")
def observability(current_user: User = Depends(get_current_user)):
    return enterprise_observability_snapshot()


@router.get("/security")
def security(current_user: User = Depends(get_current_user)):
    return security_enterprise_snapshot()


@router.get("/disaster-recovery")
def disaster_recovery(current_user: User = Depends(get_current_user)):
    return disaster_recovery_drill()


@router.get("/performance-max")
def performance_max(current_user: User = Depends(get_current_user)):
    return performance_max_plan()


@router.get("/gold-certification")
def gold_certification(current_user: User = Depends(get_current_user)):
    return gold_certification_snapshot()
