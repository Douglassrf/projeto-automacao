from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session
from app.domain.models import AdAnalysis


class AdRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, data: dict, user_id: int | None = None) -> AdAnalysis:
        if user_id is not None:
            data["user_id"] = user_id
        entity = AdAnalysis(**data)
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def list_latest(self, limit: int = 20, user_id: int | None = None) -> list[AdAnalysis]:
        stmt = select(AdAnalysis)
        if user_id is not None:
            stmt = stmt.where(AdAnalysis.user_id == user_id)
        stmt = stmt.order_by(desc(AdAnalysis.created_at)).limit(limit)
        return list(self.db.scalars(stmt).all())

    def summary(self, user_id: int | None = None) -> dict:
        total_stmt = select(func.count(AdAnalysis.id))
        winners_stmt = select(func.count(AdAnalysis.id)).where(AdAnalysis.active_ads >= 15)
        avg_score_stmt = select(func.avg(AdAnalysis.score))
        avg_connect_stmt = select(func.avg(AdAnalysis.connect_rate))
        if user_id is not None:
            total_stmt = total_stmt.where(AdAnalysis.user_id == user_id)
            winners_stmt = winners_stmt.where(AdAnalysis.user_id == user_id)
            avg_score_stmt = avg_score_stmt.where(AdAnalysis.user_id == user_id)
            avg_connect_stmt = avg_connect_stmt.where(AdAnalysis.user_id == user_id)
        total = self.db.scalar(total_stmt) or 0
        winners = self.db.scalar(winners_stmt) or 0
        avg_score = self.db.scalar(avg_score_stmt) or 0
        avg_connect = self.db.scalar(avg_connect_stmt) or 0
        return {
            "total_analyses": total,
            "winners": winners,
            "average_score": round(float(avg_score), 2),
            "average_connect_rate": round(float(avg_connect), 2),
            "latest": self.list_latest(10, user_id=user_id),
        }
