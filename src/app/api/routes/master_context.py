from fastapi import APIRouter

from app.services.master_context import MasterContextStore


router = APIRouter(prefix="/master-context", tags=["Master Context"])


@router.get("/health")
def health():
    return MasterContextStore().health()


@router.get("/init")
def init():
    return MasterContextStore().ensure_initialized()


@router.get("/snapshot")
def snapshot():
    return MasterContextStore().snapshot()


@router.get("/startup-checklist")
def startup_checklist():
    return MasterContextStore().startup_checklist()


@router.post("/update")
def update(payload: dict):
    return MasterContextStore().update(payload)


@router.post("/record-mission")
def record_mission(payload: dict):
    return MasterContextStore().record_mission(
        mission_number=int(payload.get("mission_number")),
        title=str(payload.get("title") or ""),
        status=str(payload.get("status") or "ok"),
        summary=str(payload.get("summary") or ""),
        next_mission=payload.get("next_mission"),
    )
