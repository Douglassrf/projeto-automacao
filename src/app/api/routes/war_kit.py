from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.war_kit import WarKitRequest, WarKitResponse
from app.services.war_kit_generator import WarKitGenerator

router = APIRouter(prefix="/war-kit", tags=["AI War Kit Generator"])


@router.post("/generate", response_model=WarKitResponse)
def generate_war_kit(payload: WarKitRequest, current_user: User = Depends(get_current_user)):
    try:
        return WarKitGenerator().generate(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha ao gerar kit de campanha: {exc}") from exc
