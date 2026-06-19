from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.domain.models import User
from app.services.campaign_intelligence_safe import CampaignIntelligenceSafe


router = APIRouter(prefix="/campaign-intelligence-safe", tags=["Campaign Intelligence Safe"])


@router.get("/health")
def health(current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceSafe().health()


@router.get("/summary")
def summary(product_name: str = "", niche: str = "", limit: int = 300, current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceSafe().analyze(product_name=product_name, niche=niche, limit=limit)


@router.get("/summary/mock")
def summary_mock(current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceSafe().analyze(
        product_name="Ebook de Receitas Fitness",
        niche="emagrecimento",
        limit=300,
    )


@router.get("/mock-seed")
def mock_seed(current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceSafe().mock_seed()
