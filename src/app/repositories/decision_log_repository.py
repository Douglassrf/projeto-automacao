from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.domain.models import DecisionLog
from app.schemas.decision_logs import DecisionLogCreate


class DecisionLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: DecisionLogCreate) -> DecisionLog:
        record = DecisionLog(**payload.model_dump())
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_latest(self, limit: int = 25, user_id: int | None = None) -> list[DecisionLog]:
        query = self.db.query(DecisionLog)
        if user_id is not None:
            query = query.filter(DecisionLog.user_id == user_id)
        return query.order_by(desc(DecisionLog.timestamp), desc(DecisionLog.id)).limit(limit).all()
