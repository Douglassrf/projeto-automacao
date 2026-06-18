from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.domain.models import User
from app.schemas.campaign_intelligence import (
    AdLibraryBenchmarkCreateRequest,
    AdLibraryBenchmarkResponse,
    CampaignCreateRequest,
    CampaignDecisionResponse,
    CampaignMetricCreateRequest,
    FinancialMetricCreateRequest,
    FinancialMetricResponse,
    DecisionLoopRequest,
    DecisionLoopResponse,
    CampaignMetricResponse,
    CampaignResponse,
    EvaluateCampaignRequest,
    IntelligenceHealthResponse,
    PerformanceTicketResponse,
    MetaActionApprovalRequest,
    MetaActionExecutionRequest,
    MetaActionProposalRequest,
    MetaActionResponse,
    MetaDecisionContextResponse,
    CampaignStateSyncResponse,
    MetaCampaignSyncRequest,
    MetaCampaignSyncResponse,
    IntelligentScalingRunResponse,
    ManualRevenueEntryCreateRequest,
    ManualRevenueEntryResponse,
    ScalingRuleCreateRequest,
    ScalingRuleResponse,
)
from app.services.campaign_intelligence import CampaignIntelligenceService

router = APIRouter(prefix="/campaign-intelligence", tags=["Campaign Intelligence"])


@router.get("/health", response_model=IntelligenceHealthResponse)
def health(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceService(db).health()


@router.post("/campaigns", response_model=CampaignResponse)
def create_campaign(payload: CampaignCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceService(db).create_or_update_campaign(payload)


@router.post("/metrics", response_model=CampaignMetricResponse)
def ingest_metrics(payload: CampaignMetricCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return CampaignIntelligenceService(db).ingest_metrics(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc




@router.post("/financial-metrics", response_model=FinancialMetricResponse)
def ingest_financial_metrics(payload: FinancialMetricCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return CampaignIntelligenceService(db).ingest_financial_metric(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/scaling-rules", response_model=ScalingRuleResponse)
def create_scaling_rule(payload: ScalingRuleCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return CampaignIntelligenceService(db).create_scaling_rule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/manual-revenue", response_model=ManualRevenueEntryResponse)
def add_manual_revenue(payload: ManualRevenueEntryCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return CampaignIntelligenceService(db).add_manual_revenue(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/scaling/run", response_model=IntelligentScalingRunResponse)
def run_intelligent_scaling(dry_run: bool = True, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceService(db).run_intelligent_scaling(dry_run=dry_run, limit=limit)


@router.post("/benchmarks", response_model=AdLibraryBenchmarkResponse)
def add_benchmark(payload: AdLibraryBenchmarkCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = CampaignIntelligenceService(db).add_benchmark(payload)
    return AdLibraryBenchmarkResponse(
        id=row.id,
        niche=row.niche,
        geo=row.geo,
        language=row.language,
        creative_pattern=row.creative_pattern,
        hook_pattern=row.hook_pattern,
        days_active=row.days_active,
        estimated_strength_score=row.estimated_strength_score,
        benchmark_ctr=row.benchmark_ctr,
        source_ad_id=row.source_ad_id,
        captured_at=row.captured_at,
    )


@router.post("/evaluate", response_model=CampaignDecisionResponse)
def evaluate(payload: EvaluateCampaignRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return CampaignIntelligenceService(db).evaluate(
            internal_campaign_id=payload.internal_campaign_id,
            meta_campaign_id=payload.meta_campaign_id,
            niche=payload.niche,
            geo=payload.geo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/tickets", response_model=list[PerformanceTicketResponse])
def tickets(limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceService(db).tickets(limit=limit)


@router.post("/decision-loop", response_model=DecisionLoopResponse)
def decision_loop(payload: DecisionLoopRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceService(db).run_decision_loop(
        dry_run=payload.dry_run,
        meta_cpa_ideal=payload.meta_cpa_ideal,
        test_budget_brl=payload.test_budget_brl,
        scale_budget_brl=payload.scale_budget_brl,
        limit=payload.limit,
    )


@router.post("/meta-actions/propose", response_model=MetaActionResponse)
def propose_meta_action(payload: MetaActionProposalRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return CampaignIntelligenceService(db).propose_meta_action(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/meta-actions/pending", response_model=list[MetaActionResponse])
def pending_meta_actions(limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceService(db).pending_meta_actions(limit=limit)




@router.get("/meta-actions/decision-context", response_model=list[MetaDecisionContextResponse])
def meta_action_decision_context(limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceService(db).decision_context(limit=limit)

@router.post("/meta-actions/{request_id}/approve", response_model=MetaActionResponse)
def approve_meta_action(request_id: int, payload: MetaActionApprovalRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return CampaignIntelligenceService(db).approve_meta_action(
            request_id=request_id,
            payload_hash=payload.payload_hash,
            confirmed_by_user=payload.confirmed_by_user,
            approved_by=payload.approved_by,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc




@router.post("/meta-actions/{request_id}/execute", response_model=MetaActionResponse)
def execute_meta_action(request_id: int, payload: MetaActionExecutionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return CampaignIntelligenceService(db).execute_approved_meta_action(
            request_id=request_id,
            confirmed_by_user=payload.confirmed_by_user,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/campaigns/sync-state", response_model=CampaignStateSyncResponse)
def sync_campaign_state(payload: EvaluateCampaignRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return CampaignIntelligenceService(db).sync_campaign_state(
            internal_campaign_id=payload.internal_campaign_id,
            meta_campaign_id=payload.meta_campaign_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/campaigns/sync-meta", response_model=MetaCampaignSyncResponse)
def sync_meta_campaigns(payload: MetaCampaignSyncRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return CampaignIntelligenceService(db).sync_meta_account_campaigns(
        limit=payload.limit,
        dry_run=payload.dry_run,
    )
