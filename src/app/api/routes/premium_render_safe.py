from fastapi import APIRouter

from app.schemas.premium_render import PremiumRenderRequest
from app.services.premium_render_bridge import PremiumRenderBridge


router = APIRouter(prefix="/premium-render-safe", tags=["Premium Render Safe"])


@router.get("/health")
def health():
    return PremiumRenderBridge().health()


@router.get("/mock-run")
def mock_run():
    return PremiumRenderBridge().run_mock_cycle()


@router.post("/render")
def render(payload: PremiumRenderRequest):
    return PremiumRenderBridge().safe_render(payload=payload, product_name=payload.product_name, niche="")
