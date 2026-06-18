from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.capi_enterprise import (
    CapiBrowserPixelPayloadRequest,
    CapiBrowserPixelPayloadResponse,
    CapiEnterpriseRequest,
    CapiEnterpriseResponse,
    CapiHealthResponse,
)
from app.services.capi_enterprise import CapiEnterpriseService

router = APIRouter(prefix="/capi-enterprise", tags=["CAPI Enterprise"])


@router.get("/health", response_model=CapiHealthResponse)
def capi_health(current_user: User = Depends(get_current_user)):
    return CapiEnterpriseService().health()


@router.post("/events", response_model=CapiEnterpriseResponse)
def ingest_capi_enterprise_events(payload: CapiEnterpriseRequest, current_user: User = Depends(get_current_user)):
    try:
        return CapiEnterpriseService().ingest(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha CAPI Enterprise: {exc}") from exc


@router.post("/browser-pixel-payload", response_model=CapiBrowserPixelPayloadResponse)
def build_browser_pixel_payload(payload: CapiBrowserPixelPayloadRequest, current_user: User = Depends(get_current_user)):
    try:
        return CapiEnterpriseService().browser_pixel_payload(payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha ao gerar payload browser Pixel: {exc}") from exc
