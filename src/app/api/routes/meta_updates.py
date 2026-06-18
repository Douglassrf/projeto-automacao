from fastapi import APIRouter

from app.services.meta_update_watcher import MetaUpdateWatcher


router = APIRouter(prefix="/meta-updates", tags=["Meta Updates"])


@router.get("/health")
def meta_updates_health():
    return MetaUpdateWatcher().health()


@router.get("/list")
def list_meta_updates(limit: int = 50):
    return MetaUpdateWatcher().list_updates(limit=limit)


@router.post("/register")
def register_meta_update(payload: dict):
    return MetaUpdateWatcher().register_update(payload)


@router.post("/assess")
def assess_meta_updates(payload: dict):
    return MetaUpdateWatcher().assess_context(payload)


@router.get("/mock")
def mock_meta_update():
    return MetaUpdateWatcher().mock_update()
