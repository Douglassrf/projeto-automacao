from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.facebook_marketing import (
    CampaignPlanRequest,
    CampaignPlanResponse,
    V1MarketingRequest,
    V1MarketingResponse,
    V2DedicatedSimulationRequest,
    V2DedicatedSimulationResponse,
    V3ExecutionRequest,
    V3ExecutionResponse,
    ProductCampaignSuiteRequest,
    ProductCampaignSuiteResponse,
)
from app.services.facebook_automation import FacebookMarketingAutomationEngine

router = APIRouter(prefix="/facebook", tags=["Facebook Ads Automation V1-V3"])


@router.post("/v1/strategy", response_model=V1MarketingResponse)
def v1_strategy(payload: V1MarketingRequest, current_user: User = Depends(get_current_user)):
    return FacebookMarketingAutomationEngine().v1_strategy(payload)


@router.post("/v2/campaign-plan", response_model=CampaignPlanResponse)
def v2_campaign_plan(payload: CampaignPlanRequest, current_user: User = Depends(get_current_user)):
    return FacebookMarketingAutomationEngine().v2_campaign_plan(payload)


@router.post("/v2/simulate", response_model=V2DedicatedSimulationResponse)
def v2_simulate(payload: V2DedicatedSimulationRequest, current_user: User = Depends(get_current_user)):
    return FacebookMarketingAutomationEngine().v2_dedicated_simulation(payload)


@router.post("/campaign-suite/build", response_model=ProductCampaignSuiteResponse)
def build_campaign_suite(payload: ProductCampaignSuiteRequest, current_user: User = Depends(get_current_user)):
    return FacebookMarketingAutomationEngine().build_product_campaign_suite(payload)


@router.post("/v3/execute", response_model=V3ExecutionResponse)
def v3_execute(payload: V3ExecutionRequest, current_user: User = Depends(get_current_user)):
    try:
        return FacebookMarketingAutomationEngine().v3_execute(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha na automação Facebook Ads: {exc}",
        ) from exc
