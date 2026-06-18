from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.domain.models import User

from app.db.session import get_db
from app.integrations.affiliate_provider import AffiliateIntegrationError
from app.repositories.ad_repository import AdRepository
from app.schemas.automation import BatchProcessRequest, BatchProcessResponse
from app.services.automation_processor import AutomationProcessor

router = APIRouter(prefix="/automation", tags=["Batch Automation"])


@router.post("/process-feed", response_model=BatchProcessResponse, status_code=201)
def process_feed(payload: BatchProcessRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Processa uma lista/feed de anúncios e aplica link afiliado apenas nos vencedores."""
    try:
        processor = AutomationProcessor(AdRepository(db))
        return processor.process_feed(payload, user_id=current_user.id)
    except AffiliateIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao executar automação em lote. Verifique payload, logs e credenciais.",
        ) from exc
