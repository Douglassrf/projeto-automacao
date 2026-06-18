from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower().strip())
        return self.db.scalar(stmt)

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def create(self, *, name: str, email: str, hashed_password: str, access_level: str = "PERSONAL") -> User:
        user = User(name=name, email=email.lower().strip(), hashed_password=hashed_password, access_level=access_level)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
