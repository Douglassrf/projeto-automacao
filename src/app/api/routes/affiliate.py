from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.deps import get_current_user
from app.domain.models import User

from app.integrations.activity_logger import read_latest_affiliate_activity
from app.integrations.affiliate_provider import AffiliateIntegrationError, AffiliateProvider
from app.schemas.affiliate import AffiliateActivity, AffiliateReplaceRequest, AffiliateReplaceResponse
from app.core.route_security import affiliate_link_security_guard

router = APIRouter(prefix="/affiliate", tags=["Affiliate Integrations"])


@router.post("/replace-link", response_model=AffiliateReplaceResponse)
def replace_affiliate_link(payload: AffiliateReplaceRequest, current_user: User = Depends(get_current_user)):
    affiliate_link_security_guard(payload.model_dump(mode="json"))
    provider = AffiliateProvider()
    try:
        return provider.replace_link(payload)
    except AffiliateIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # defensive boundary for external provider failures
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Falha ao conectar com a rede de afiliados. Verifique credenciais e tente novamente.",
        ) from exc


@router.get("/activity", response_model=list[AffiliateActivity])
def latest_affiliate_activity(limit: int = Query(10, ge=1, le=100), current_user: User = Depends(get_current_user)):
    return read_latest_affiliate_activity(limit)
