from fastapi import APIRouter

from app.services.decision_feed_store import DecisionFeedStore


router = APIRouter(prefix="/decision-feed", tags=["Decision Feed"])


@router.get("/health")
def decision_feed_health():
    return DecisionFeedStore().health()


@router.get("/list")
def decision_feed_list(limit: int = 50):
    return DecisionFeedStore().list_decisions(limit=limit)


@router.get("/summary")
def decision_feed_summary(limit: int = 200):
    return DecisionFeedStore().summary(limit=limit)
