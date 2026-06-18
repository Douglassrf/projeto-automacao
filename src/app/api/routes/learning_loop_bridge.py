from fastapi import APIRouter

from app.services.learning_loop_bridge import LearningLoopBrainBridge


router = APIRouter(prefix="/learning-loop-bridge", tags=["Learning Loop Bridge"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "agent": "LearningLoopBrainBridge",
        "mode": "safe",
        "meta_real": False,
        "publish_real": False,
    }


@router.get("/mock-run")
def mock_run():
    return LearningLoopBrainBridge().run_mock_cycle()
