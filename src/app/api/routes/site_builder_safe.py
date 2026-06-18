from fastapi import APIRouter

from app.schemas.site_builder import SiteGenerateRequest
from app.services.site_builder_bridge import SiteBuilderBridge


router = APIRouter(prefix="/site-builder-safe", tags=["Site Builder Safe"])


@router.get("/health")
def health():
    return SiteBuilderBridge().health()


@router.get("/mock-run")
def mock_run():
    return SiteBuilderBridge().run_mock_cycle()


@router.post("/generate")
def generate(payload: SiteGenerateRequest):
    return SiteBuilderBridge().safe_generate(payload=payload, product_name=payload.offer.product_name, niche=payload.offer.niche)
