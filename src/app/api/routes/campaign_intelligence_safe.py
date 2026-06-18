from fastapi import APIRouter

from app.services.campaign_intelligence_safe import CampaignIntelligenceSafe


router = APIRouter(prefix="/campaign-intelligence-safe", tags=["Campaign Intelligence Safe"])


@router.get("/health")
def health():
    return CampaignIntelligenceSafe().health()


@router.get("/summary")
def summary(product_name: str = "", niche: str = "", limit: int = 300):
    return CampaignIntelligenceSafe().analyze(product_name=product_name, niche=niche, limit=limit)


@router.get("/summary/mock")
def summary_mock():
    return CampaignIntelligenceSafe().analyze(
        product_name="Ebook de Receitas Fitness",
        niche="emagrecimento",
        limit=300,
    )


@router.get("/mock-seed")
def mock_seed():
    return CampaignIntelligenceSafe().mock_seed()
