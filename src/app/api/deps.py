from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.domain.models import User
from app.repositories.user_repository import UserRepository

security = HTTPBearer(auto_error=False)


def _demo_user_from_settings() -> User:
    settings = get_settings()
    return User(
        id=0,
        name=settings.default_admin_name,
        email=settings.default_admin_email,
        access_level="DEV",
        hashed_password="",
        is_active=True,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()
    if not settings.auth_required:
        try:
            user = UserRepository(db).get_by_email(settings.default_admin_email)
            if user:
                return user
        except SQLAlchemyError:
            return _demo_user_from_settings()
        return _demo_user_from_settings()

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login necessário.")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except (InvalidTokenError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.") from exc

    user = UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo ou inexistente.")
    return user
