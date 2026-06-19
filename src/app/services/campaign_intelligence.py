from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from uuid import uuid4

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import AdLibraryBenchmark, Campaign, CampaignMetric, FinancialMetric, ManualRevenueEntry, MetaActionRequest, PerformanceTicket, ScalingRule
from app.integrations.meta_marketing import MetaMarketingClient, MetaMarketingError
from app.repositories.decision_log_repository import DecisionLogRepository
from app.services.observability import immutable_audit_event
from app.schemas.decision_logs import DecisionLogCreate
from app.schemas.campaign_intelligence import (
    AdLibraryBenchmarkCreateRequest,
    CampaignCreateRequest,
    CampaignDecisionResponse,
    CampaignMetricCreateRequest,
    FinancialMetricCreateRequest,
    FinancialMetricResponse,
    DecisionLoopActionResponse,
    DecisionLoopResponse,
    CampaignMetricResponse,
    CampaignResponse,
    IntelligenceHealthResponse,
    PerformanceTicketResponse,
    MetaActionProposalRequest,
    MetaActionResponse,
    CampaignStateSyncResponse,
    MetaCampaignSyncResponse,
    MetaCampaignSyncItem,
    MetaDecisionContextResponse,
    IntelligentScalingResponse,
    IntelligentScalingRunResponse,
    ManualRevenueEntryCreateRequest,
    ManualRevenueEntryResponse,
    ScalingRuleCreateRequest,
    ScalingRuleResponse,
)


class CampaignIntelligenceService:
    """Cruza campanhas reais, métricas internas e benchmarks minerados da Ad Library."""

    def __init__(self, db: Session, meta_client: MetaMarketingClient | None = None) -> None:
        self.db = db
        self.meta_client = meta_client or MetaMarketingClient()
        self.settings = get_settings()

    def create_or_update_campaign(self, payload: CampaignCreateRequest) -> CampaignResponse:
        campaign = self.db.query(Campaign).filter(Campaign.internal_campaign_id == payload.internal_campaign_id).first()
        if not campaign and payload.meta_campaign_id:
            campaign = self.db.query(Campaign).filter(Campaign.meta_campaign_id == payload.meta_campaign_id).first()
        if not campaign:
            campaign = Campaign(**payload.model_dump())
            self.db.add(campaign)
        else:
            for key, value in payload.model_dump().items():
                setattr(campaign, key, value)
        if not campaign.currency_code:
            campaign.currency_code = self.settings.currency_code
        if not getattr(campaign, "currency_ad_account", None):
            campaign.currency_ad_account = self.settings.currency_ad_account
        if not getattr(campaign, "currency_sales", None):
            campaign.currency_sales = self.settings.currency_sales
        if not campaign.desired_budget:
            campaign.desired_budget = campaign.daily_budget or self.settings.test_budget_brl
        if not campaign.real_budget:
            campaign.real_budget = campaign.daily_budget or 0
        campaign.budget_drift_detected = bool(
            campaign.desired_budget
            and campaign.real_budget
            and abs(float(campaign.desired_budget) - float(campaign.real_budget)) >= 0.01
        )
        self.db.commit()
        self.db.refresh(campaign)
        return self._campaign_response(campaign)

    def ingest_metrics(self, payload: CampaignMetricCreateRequest) -> CampaignMetricResponse:
        campaign = self._find_campaign(payload.internal_campaign_id, payload.meta_campaign_id)
        fx = payload.exchange_rate_to_brl or self._exchange_rate_to_brl(payload.revenue_currency or campaign.currency_sales)
        revenue_brl = payload.revenue_brl or (payload.revenue_amount * fx if payload.revenue_amount else payload.roas * payload.spend)
        unified_roas_brl = payload.unified_roas_brl or (revenue_brl / payload.spend if payload.spend else 0)
        metric = CampaignMetric(
            campaign_id=campaign.id,
            ctr=payload.ctr,
            cpc=payload.cpc,
            cpm=payload.cpm,
            spend=payload.spend,
            purchases=payload.purchases,
            cost_per_purchase=payload.cost_per_purchase,
            roas=payload.roas,
            revenue_amount=payload.revenue_amount,
            revenue_currency=(payload.revenue_currency or campaign.currency_sales).upper(),
            exchange_rate_to_brl=fx,
            revenue_brl=revenue_brl,
            unified_roas_brl=unified_roas_brl,
            connect_rate=payload.connect_rate,
            checkout_rate=payload.checkout_rate,
            capi_status=payload.capi_status,
            source=payload.source,
        )
        campaign.spend_today = payload.spend
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return self._metric_response(metric, payload)

    def ingest_financial_metric(self, payload: FinancialMetricCreateRequest) -> FinancialMetricResponse:
        campaign = self._find_campaign(payload.internal_campaign_id, payload.meta_campaign_id)
        sales_currency = (payload.revenue_currency or campaign.currency_sales or self.settings.currency_sales).upper()
        fx = float(payload.exchange_rate or self._exchange_rate_to_brl(sales_currency))
        fx_validated = bool(fx > 0 and (sales_currency == "BRL" or payload.exchange_rate > 0 or payload.exchange_rate_source in {"manual", "checkout", "crm", "api", "env"}))
        revenue_brl = payload.revenue_amount * fx if fx > 0 else 0
        roas_brl = revenue_brl / payload.spend_brl if payload.spend_brl else 0
        row = FinancialMetric(
            campaign_id=campaign.id,
            spend_brl=payload.spend_brl,
            revenue_amount=payload.revenue_amount,
            revenue_currency=sales_currency,
            exchange_rate=fx,
            revenue_brl=revenue_brl,
            calculated_roas_brl=roas_brl,
            exchange_rate_source=payload.exchange_rate_source,
            fx_validated=fx_validated,
            raw_payload_json=json.dumps(payload.raw_payload or {}, ensure_ascii=False, sort_keys=True),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._financial_metric_response(row, payload)

    def create_scaling_rule(self, payload: ScalingRuleCreateRequest) -> ScalingRuleResponse:
        campaign = self._find_campaign(payload.internal_campaign_id, payload.meta_campaign_id)
        existing = (
            self.db.query(ScalingRule)
            .filter(ScalingRule.campaign_id == campaign.id, ScalingRule.is_active == True)  # noqa: E712
            .order_by(desc(ScalingRule.created_at))
            .first()
        )
        data = payload.model_dump()
        data.pop("internal_campaign_id", None)
        data.pop("meta_campaign_id", None)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            existing.meta_campaign_id = campaign.meta_campaign_id
            existing.updated_at = datetime.now(UTC)
            row = existing
        else:
            row = ScalingRule(campaign_id=campaign.id, meta_campaign_id=campaign.meta_campaign_id, **data)
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._scaling_rule_response(row, payload)

    def add_manual_revenue(self, payload: ManualRevenueEntryCreateRequest) -> ManualRevenueEntryResponse:
        campaign = self._find_campaign(payload.internal_campaign_id, payload.meta_campaign_id)
        currency = (payload.currency or campaign.currency_sales or self.settings.currency_sales).upper()
        fx = float(payload.exchange_rate_to_brl or self._exchange_rate_to_brl(currency))
        if fx <= 0:
            raise ValueError("exchange_rate_to_brl válido é obrigatório para receita em moeda estrangeira.")
        revenue_brl = payload.revenue_amount * fx
        row = ManualRevenueEntry(
            campaign_id=campaign.id,
            meta_campaign_id=campaign.meta_campaign_id,
            revenue_amount=payload.revenue_amount,
            currency=currency,
            exchange_rate_to_brl=fx,
            revenue_brl=revenue_brl,
            sales_count=payload.sales_count,
            notes=payload.notes,
            created_by=payload.created_by,
        )
        self.db.add(row)
        # Also feed the financial_metrics layer so the existing ROAS dashboards keep working.
        spend_brl = campaign.spend_today or campaign.daily_budget or self.settings.test_budget_brl
        financial = FinancialMetric(
            campaign_id=campaign.id,
            spend_brl=spend_brl,
            revenue_amount=payload.revenue_amount,
            revenue_currency=currency,
            exchange_rate=fx,
            revenue_brl=revenue_brl,
            calculated_roas_brl=(revenue_brl / spend_brl if spend_brl else 0),
            exchange_rate_source="manual_revenue_entry",
            fx_validated=True,
            raw_payload_json=json.dumps({
                "source": "manual_revenue_entry",
                "manual_revenue_created_by": payload.created_by,
                "sales_count": payload.sales_count,
            }, ensure_ascii=False, sort_keys=True),
        )
        self.db.add(financial)
        self.db.commit()
        self.db.refresh(row)
        return self._manual_revenue_response(row, payload)

    def run_intelligent_scaling(self, dry_run: bool = True, limit: int = 50) -> IntelligentScalingRunResponse:
        campaigns = (
            self.db.query(Campaign)
            .filter(Campaign.status.in_(["ACTIVE", "active"]))
            .order_by(Campaign.id.asc())
            .limit(limit)
            .all()
        )
        results: list[IntelligentScalingResponse] = []
        proposed = 0
        for campaign in campaigns:
            rule = (
                self.db.query(ScalingRule)
                .filter(ScalingRule.campaign_id == campaign.id, ScalingRule.is_active == True)  # noqa: E712
                .order_by(desc(ScalingRule.created_at))
                .first()
            )
            if not rule:
                continue
            response = self._evaluate_scaling_rule(campaign, rule, dry_run=dry_run)
            if response.action == "SCALE_BUDGET" and response.action_id:
                proposed += 1
            results.append(response)
        self.db.commit()
        return IntelligentScalingRunResponse(
            processed=len(campaigns),
            proposed=proposed,
            dry_run=dry_run,
            results=results,
        )

    def add_benchmark(self, payload: AdLibraryBenchmarkCreateRequest):
        benchmark = AdLibraryBenchmark(**payload.model_dump())
        self.db.add(benchmark)
        self.db.commit()
        self.db.refresh(benchmark)
        return benchmark

    def evaluate(self, internal_campaign_id: str | None, meta_campaign_id: str | None, niche: str | None = None, geo: str | None = None) -> CampaignDecisionResponse:
        campaign = self._find_campaign(internal_campaign_id, meta_campaign_id)
        latest = self.db.query(CampaignMetric).filter(CampaignMetric.campaign_id == campaign.id).order_by(desc(CampaignMetric.created_at)).first()
        benchmark_ctr = self._benchmark_ctr(niche or campaign.product_name, geo)
        tickets: list[PerformanceTicket] = []
        actions: list[str] = []

        if not latest:
            ticket = self._open_ticket(campaign, "yellow", "NO_METRICS", "monitor", "Ainda não há métricas para decidir. Importe CSV ou conecte Meta Insights API.")
            tickets.append(ticket)
            return self._decision_response(campaign, latest, benchmark_ctr, "yellow", tickets, actions + ["monitor"], "Sem métricas, o agente só observa.")

        if latest.capi_status != "ok":
            tickets.append(self._open_ticket(campaign, "red", "CAPI_ERROR", "activate_capi_fallback", "Erro/degradação na CAPI. Ative fallback para não perder dados de conversão."))
            actions.append("activate_capi_fallback")

        if latest.connect_rate and latest.connect_rate < 75:
            tickets.append(self._open_ticket(campaign, "yellow", "LOW_CONNECT_RATE", "fix_landing_page", f"Connect Rate {latest.connect_rate:.1f}% abaixo de 75%. Corrija carregamento, domínio ou checkout antes de culpar o criativo."))
            actions.append("fix_landing_page")

        if campaign.target_cpa and latest.cost_per_purchase > campaign.target_cpa and latest.purchases > 0:
            tickets.append(self._open_ticket(campaign, "red", "CPA_ABOVE_TARGET", "pause_campaign", f"CPA R${latest.cost_per_purchase:.2f} passou da meta R${campaign.target_cpa:.2f}. Pausar evita prejuízo."))
            actions.append("pause_campaign")

        if latest.roas < 1.0 and latest.spend > 0:
            tickets.append(self._open_ticket(campaign, "yellow", "ROAS_BELOW_1", "reduce_budget_50", f"ROAS {latest.roas:.2f} abaixo de 1.0. Reduza orçamento e teste novo criativo V2."))
            actions.append("reduce_budget_50")
            actions.append("generate_new_assets")

        if benchmark_ctr is not None and latest.ctr > benchmark_ctr and (latest.unified_roas_brl or latest.roas) >= max(self.settings.scale_min_roas, campaign.target_roas * 0.8):
            tickets.append(self._open_ticket(campaign, "green", "SCALE_BUDGET_TO_50_BRL", "scale_budget", f"Performance validada: CTR {latest.ctr:.2f}% acima do benchmark {benchmark_ctr:.2f}%, ROAS unificado BRL {(latest.unified_roas_brl or latest.roas):.2f} aceitável e CPA dentro da meta. Sugestão: escalar de R$ {self._desired_budget(campaign):.2f} para R$ {self.settings.scale_budget_brl:.2f}."))
            actions.append("scale_budget")
            actions.append("scale_budget_20")

        if not tickets:
            tickets.append(self._open_ticket(campaign, "info", "STABLE_MONITORING", "monitor", "Campanha está estável. Mantenha observação antes de mexer."))
            actions.append("monitor")

        color = "red" if any(t.severity == "red" for t in tickets) else "yellow" if any(t.severity == "yellow" for t in tickets) else "green" if any(t.severity == "green" for t in tickets) else "info"
        reasoning = self._build_reasoning(latest, campaign, benchmark_ctr, actions)
        self.db.commit()
        for t in tickets:
            self.db.refresh(t)
        return self._decision_response(campaign, latest, benchmark_ctr, color, tickets, actions, reasoning)

    def health(self) -> IntelligenceHealthResponse:
        return IntelligenceHealthResponse(
            campaigns=self.db.query(Campaign).count(),
            metrics=self.db.query(CampaignMetric).count(),
            benchmarks=self.db.query(AdLibraryBenchmark).count(),
            open_tickets=self.db.query(PerformanceTicket).filter(PerformanceTicket.status == "open").count(),
            schema_keys={
                "campaign_pk": "campaigns.id",
                "meta_link_key": "campaigns.meta_campaign_id",
                "daily_spend_field": "campaigns.spend_today",
                "budget_field": "campaigns.desired_budget",
                "real_budget_field": "campaigns.real_budget",
                "currency": self.settings.currency_code,
                "metrics_table": "campaign_metrics",
                "decision_table": "performance_tickets + decision_logs",
            },
            agent_visibility="ok" if self.db.query(Campaign).count() >= 0 else "blind",
        )

    def tickets(self, limit: int = 50) -> list[PerformanceTicketResponse]:
        rows = self.db.query(PerformanceTicket).order_by(desc(PerformanceTicket.created_at)).limit(limit).all()
        return [self._ticket_response(row) for row in rows]

    def propose_meta_action(self, payload: MetaActionProposalRequest) -> MetaActionResponse:
        """Create a pending approval record instead of touching Meta directly.

        This is the Abstraction Layer: AI proposes, DB stores, human approves,
        and only then the gateway can call Meta.
        """
        campaign = self._find_campaign(payload.internal_campaign_id, payload.meta_campaign_id)
        target_id = campaign.meta_adset_id if payload.target == "adset" else campaign.meta_campaign_id
        proposed_payload = {
            "action": payload.action,
            "target": payload.target,
            "target_id": target_id,
            "campaign_pk": campaign.id,
            "internal_campaign_id": campaign.internal_campaign_id,
            "meta_campaign_id": campaign.meta_campaign_id,
            "meta_adset_id": campaign.meta_adset_id,
            "new_daily_budget_brl": payload.new_daily_budget_brl,
            "reasoning": payload.reasoning,
        }
        payload_hash = hashlib.sha256(json.dumps(proposed_payload, sort_keys=True).encode("utf-8")).hexdigest()
        row = MetaActionRequest(
            request_key=f"meta_action_{uuid4().hex}",
            campaign_id=campaign.id,
            meta_campaign_id=campaign.meta_campaign_id,
            meta_adset_id=campaign.meta_adset_id,
            action=payload.action,
            target=payload.target,
            proposed_payload_json=json.dumps(proposed_payload, ensure_ascii=False, sort_keys=True),
            payload_hash=payload_hash,
            status="pending_approval",
        )
        self.db.add(row)
        self._open_ticket(campaign, "yellow", "META_ACTION_PENDING_APPROVAL", payload.action, payload.reasoning or "Ação proposta aguardando aprovação humana.")
        self.db.commit()
        self.db.refresh(row)
        return self._meta_action_response(row)

    def pending_meta_actions(self, limit: int = 50) -> list[MetaActionResponse]:
        rows = (
            self.db.query(MetaActionRequest)
            .filter(MetaActionRequest.status == "pending_approval")
            .order_by(desc(MetaActionRequest.created_at))
            .limit(limit)
            .all()
        )
        return [self._meta_action_response(row) for row in rows]

    def approve_meta_action(self, request_id: int, payload_hash: str, confirmed_by_user: bool, approved_by: str, dry_run: bool = True) -> MetaActionResponse:
        """Mark a pending Meta action as approved; do not execute it here.

        Production safety rule: approval and execution are separate phases.
        The Sync Worker and Decision Loop must never process a pending action;
        only rows with status=approved can reach the Meta write gateway.
        """
        row = self.db.query(MetaActionRequest).filter(MetaActionRequest.id == request_id).first()
        if not row:
            raise ValueError("Pedido de ação Meta não encontrado.")
        if row.status != "pending_approval":
            raise ValueError(f"Pedido não está pendente; status atual: {row.status}.")
        if row.payload_hash != payload_hash:
            raise ValueError("Hash do payload não confere. Reabra o preview antes de aprovar.")
        if not confirmed_by_user:
            raise ValueError("confirmed_by_user=true é obrigatório para aprovar ação Meta.")

        campaign = self.db.query(Campaign).filter(Campaign.id == row.campaign_id).first()
        row.approved_by = approved_by
        row.approved_at = datetime.now(UTC)
        row.status = "approved"
        row.executed_response_json = json.dumps({
            "status": "approved_pending_execution",
            "dry_run": dry_run,
            "message": "Ação aprovada, mas ainda não executada. Use /execute para enviar à Meta."
        }, ensure_ascii=False, sort_keys=True)
        DecisionLogRepository(self.db).create(DecisionLogCreate(
            campaign_id=campaign.meta_campaign_id or campaign.internal_campaign_id,
            product_name=campaign.product_name or campaign.internal_campaign_id,
            reason_code="META_ACTION_APPROVED_PENDING_EXECUTION",
            metric_name="approval_layer",
            metric_value=1,
            threshold_value=1,
            severity="warning",
            tag_label="Ação aprovada",
            action_taken=row.action,
            reasoning=f"Ação {row.action} aprovada por {approved_by}. Nenhuma escrita Meta foi executada nesta etapa.",
            metadata_json=self._metrics_metadata(campaign, extra={
                "approval_status": "approved",
                "approved_by": approved_by,
                "action_id": row.id,
                "payload_hash": row.payload_hash,
            }),
        ))
        self.db.commit()
        self.db.refresh(row)
        return self._meta_action_response(row)

    def _real_mode_guardrails(self) -> list[str]:
        """Guardrails de ambiente para qualquer escrita real na Meta (C04).

        execute_approved_meta_action() é um segundo caminho capaz de acionar
        MetaMarketingClient.apply_campaign_action() de verdade, independente
        do MetaCampaignOperator/FacebookMarketingAutomationEngine — por isso
        replica aqui as mesmas checagens server-side (meta_env,
        meta_allow_production_real, meta_autopublish) já exigidas nos outros
        dois caminhos, em vez de depender só de META_DRY_RUN.
        """
        if self.meta_client.dry_run:
            return []
        reasons: list[str] = []
        allowed_envs = {"sandbox", "test_account", "production"}
        meta_env = getattr(self.settings, "meta_env", None)
        if meta_env not in allowed_envs:
            reasons.append(f"meta_env_invalido:{meta_env}")
        elif meta_env == "production" and not getattr(self.settings, "meta_allow_production_real", False):
            reasons.append("production_real_not_allowed")
        if not getattr(self.settings, "meta_autopublish", False):
            reasons.append("autopublish_disabled")
        return reasons

    def execute_approved_meta_action(self, request_id: int, confirmed_by_user: bool, dry_run: bool = True) -> MetaActionResponse:
        """Execute only an approved Meta action. Pending actions are ignored."""
        row = self.db.query(MetaActionRequest).filter(MetaActionRequest.id == request_id).first()
        if not row:
            raise ValueError("Pedido de ação Meta não encontrado.")
        if row.status != "approved":
            raise ValueError(f"Apenas ações approved podem ser executadas; status atual: {row.status}.")
        if not confirmed_by_user:
            raise ValueError("confirmed_by_user=true é obrigatório para executar ação Meta.")

        campaign = self.db.query(Campaign).filter(Campaign.id == row.campaign_id).first()
        proposed = json.loads(row.proposed_payload_json or "{}")

        real_mode_blocked_reasons = self._real_mode_guardrails()
        guard_blocked = bool(real_mode_blocked_reasons) and not dry_run
        if guard_blocked:
            block_message = (
                "Execução real bloqueada por guardrails de ambiente: "
                + ", ".join(real_mode_blocked_reasons) + "."
            )
            response = {
                "dry_run": True,
                "status": "blocked_for_manual_review",
                "action": row.action,
                "message": block_message,
                "messages": [block_message],
            }
            executed = False
            immutable_audit_event(
                actor="CampaignIntelligenceService",
                action="campaign_intelligence.execute_approved_meta_action.blocked",
                resource_type="meta_action_request",
                resource_id=str(row.id),
                status="blocked",
                details={"meta_action": row.action, "reasons": real_mode_blocked_reasons},
            )
        else:
            response, executed = self._apply_loop_action(
                action=row.action,
                campaign=campaign,
                new_daily_budget_brl=proposed.get("new_daily_budget_brl"),
                dry_run=dry_run,
            )
            if response.get("status") == "executed" and not response.get("dry_run", True):
                immutable_audit_event(
                    actor="CampaignIntelligenceService",
                    action="campaign_intelligence.execute_approved_meta_action.published",
                    resource_type="meta_action_request",
                    resource_id=str(row.id),
                    status="ok",
                    details={"meta_action": row.action},
                )
        row.executed_response_json = json.dumps(response, ensure_ascii=False, sort_keys=True)
        if response.get("status") in {"executed", "simulated"}:
            row.status = "executed_dry_run" if response.get("dry_run") else "executed"
            row.executed_at = datetime.now(UTC)
            if row.action == "pause_campaign" and executed:
                campaign.desired_status = "PAUSED"
                campaign.status = "PAUSED"
        else:
            row.status = "failed"
            row.failure_reason = response.get("message") or response.get("reason") or "Falha desconhecida."
        DecisionLogRepository(self.db).create(DecisionLogCreate(
            campaign_id=campaign.meta_campaign_id or campaign.internal_campaign_id,
            product_name=campaign.product_name or campaign.internal_campaign_id,
            reason_code="META_ACTION_EXECUTED" if not dry_run else "META_ACTION_EXECUTED_DRY_RUN",
            metric_name="execution_layer",
            metric_value=1,
            threshold_value=1,
            severity="warning" if dry_run else "danger",
            tag_label="Execução Meta",
            action_taken=row.action,
            reasoning=f"Ação {row.action} executada após aprovação humana. Dry-run={dry_run}.",
            metadata_json=self._metrics_metadata(campaign, extra={
                "execution_status": row.status,
                "action_id": row.id,
                "dry_run": dry_run,
                "meta_response": response,
            }),
        ))
        self.db.commit()
        self.db.refresh(row)
        return self._meta_action_response(row)

    def decision_context(self, limit: int = 50) -> list[MetaDecisionContextResponse]:
        rows = (
            self.db.query(MetaActionRequest)
            .order_by(desc(MetaActionRequest.created_at))
            .limit(limit)
            .all()
        )
        payload: list[MetaDecisionContextResponse] = []
        for row in rows:
            campaign = self.db.query(Campaign).filter(Campaign.id == row.campaign_id).first()
            latest = (
                self.db.query(CampaignMetric)
                .filter(CampaignMetric.campaign_id == row.campaign_id)
                .order_by(desc(CampaignMetric.created_at))
                .first()
            )
            proposed = json.loads(row.proposed_payload_json or "{}")
            payload.append(MetaDecisionContextResponse(
                action_id=row.id,
                campaign_id=row.campaign_id,
                meta_campaign_id=row.meta_campaign_id,
                action=row.action,
                status=row.status,
                reason=str(proposed.get("reason") or proposed.get("reasoning") or ""),
                payload_hash=row.payload_hash,
                ctr=latest.ctr if latest else 0,
                cpa=latest.cost_per_purchase if latest else 0,
                roas=latest.roas if latest else 0,
                spend=latest.spend if latest else (campaign.spend_today if campaign else 0),
                daily_budget=campaign.daily_budget if campaign else 0,
                desired_budget=campaign.desired_budget if campaign else 0,
                real_budget=campaign.real_budget if campaign else 0,
                budget_drift_detected=campaign.budget_drift_detected if campaign else False,
                desired_status=campaign.desired_status if campaign else "UNKNOWN",
                real_status=campaign.real_status if campaign else "UNKNOWN",
                reasoning=str(proposed.get("reasoning") or "Ação aguardando decisão humana."),
                created_at=row.created_at,
            ))
        return payload

    def sync_campaign_state(self, internal_campaign_id: str | None = None, meta_campaign_id: str | None = None) -> CampaignStateSyncResponse:
        campaign = self._find_campaign(internal_campaign_id, meta_campaign_id)
        real_status = self.meta_client.get_campaign_status(campaign.meta_campaign_id) if campaign.meta_campaign_id else "UNKNOWN"
        old_real = campaign.real_status or "UNKNOWN"
        campaign.real_status = real_status
        divergence = bool(campaign.desired_status and real_status != "UNKNOWN" and campaign.desired_status.upper() != real_status.upper())
        reason = "Estado sincronizado."
        if divergence:
            reason = "Divergência detectada entre estado desejado e estado real; pode ter sido ação humana externa ou falha de sincronização."
            self._open_ticket(campaign, "yellow", "CAMPAIGN_STATE_DIVERGENCE", "monitor", reason)
        elif old_real != real_status:
            reason = f"Estado real atualizado de {old_real} para {real_status}."
        campaign.last_state_sync_reason = reason
        self.db.commit()
        return CampaignStateSyncResponse(
            campaign_pk=campaign.id,
            internal_campaign_id=campaign.internal_campaign_id,
            meta_campaign_id=campaign.meta_campaign_id,
            desired_status=campaign.desired_status,
            real_status=campaign.real_status,
            divergence_detected=divergence,
            reason=reason,
        )



    def _create_pending_meta_action(
        self,
        campaign: Campaign,
        action: str,
        reason: str,
        reasoning: str,
        target: str = "campaign",
        new_daily_budget_brl: float | None = None,
    ) -> MetaActionRequest:
        existing = (
            self.db.query(MetaActionRequest)
            .filter(
                MetaActionRequest.campaign_id == campaign.id,
                MetaActionRequest.action == action,
                MetaActionRequest.status == "pending_approval",
            )
            .order_by(desc(MetaActionRequest.created_at))
            .first()
        )
        if existing:
            existing.created_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        target_id = campaign.meta_adset_id if target == "adset" else campaign.meta_campaign_id
        proposed_payload = {
            "action": action,
            "target": target,
            "target_id": target_id,
            "campaign_pk": campaign.id,
            "internal_campaign_id": campaign.internal_campaign_id,
            "meta_campaign_id": campaign.meta_campaign_id,
            "meta_adset_id": campaign.meta_adset_id,
            "new_daily_budget_brl": new_daily_budget_brl,
            "reason": reason,
            "reasoning": reasoning,
        }
        payload_hash = hashlib.sha256(json.dumps(proposed_payload, sort_keys=True).encode("utf-8")).hexdigest()
        row = MetaActionRequest(
            request_key=f"meta_action_{uuid4().hex}",
            campaign_id=campaign.id,
            meta_campaign_id=campaign.meta_campaign_id,
            meta_adset_id=campaign.meta_adset_id,
            action=action,
            target=target,
            proposed_payload_json=json.dumps(proposed_payload, ensure_ascii=False, sort_keys=True),
            payload_hash=payload_hash,
            status="pending_approval",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def sync_meta_account_campaigns(self, limit: int = 100, dry_run: bool = True) -> MetaCampaignSyncResponse:
        """Synchronize Meta campaigns into local Campaign + metrics tables.

        Safe by default. It reads Meta (or dry-run sample), upserts campaigns,
        saves a metrics snapshot and opens a ticket when desired_status differs
        from actual Meta status. This is the stateful memory layer for the
        AI Agency Operator dashboard.
        """
        rows = self.meta_client.list_campaigns_with_metrics_today(limit=limit)
        items: list[MetaCampaignSyncItem] = []
        created = 0
        updated = 0
        drift_count = 0
        decision_repo = DecisionLogRepository(self.db)

        for row in rows:
            meta_campaign_id = row.get("meta_campaign_id", "")
            campaign = self.db.query(Campaign).filter(Campaign.meta_campaign_id == meta_campaign_id).first()
            is_new = campaign is None
            if campaign is None:
                campaign = Campaign(
                    internal_campaign_id=f"meta_sync_{meta_campaign_id}",
                    meta_campaign_id=meta_campaign_id,
                    product_name=row.get("name", meta_campaign_id),
                    strategy_version="V1",
                    status=row.get("status_real", "UNKNOWN"),
                    desired_status=row.get("status_real", "UNKNOWN"),
                    real_status=row.get("status_real", "UNKNOWN"),
                    daily_budget=self.settings.test_budget_brl,
                    spend_today=float(row.get("spend_today") or 0),
                    desired_budget=self.settings.test_budget_brl,
                    real_budget=float(row.get("daily_budget") or 0),
                    currency_code=self.settings.currency_code,
                    currency_ad_account=self.settings.currency_ad_account,
                    currency_sales=self.settings.currency_sales,
                )
                self.db.add(campaign)
                created += 1
            else:
                updated += 1
                campaign.product_name = row.get("name", campaign.product_name)
                campaign.real_status = row.get("status_real", campaign.real_status or "UNKNOWN")
                campaign.status = campaign.status or campaign.real_status
                if not campaign.desired_status:
                    campaign.desired_status = campaign.real_status
                campaign.real_budget = float(row.get("daily_budget") or campaign.real_budget or 0)
                if not campaign.desired_budget:
                    campaign.desired_budget = campaign.daily_budget or self.settings.test_budget_brl
                campaign.daily_budget = campaign.desired_budget
                campaign.currency_code = campaign.currency_code or self.settings.currency_code
                campaign.currency_ad_account = campaign.currency_ad_account or self.settings.currency_ad_account
                campaign.currency_sales = campaign.currency_sales or self.settings.currency_sales
                campaign.spend_today = float(row.get("spend_today") or 0)

            self.db.flush()
            metric = CampaignMetric(
                campaign_id=campaign.id,
                ctr=float(row.get("ctr") or 0),
                spend=float(row.get("spend_today") or 0),
                revenue_currency=campaign.currency_sales or self.settings.currency_sales,
                exchange_rate_to_brl=self._exchange_rate_to_brl(campaign.currency_sales or self.settings.currency_sales),
                source="dry_run" if dry_run or self.meta_client.dry_run else "meta_api",
            )
            self.db.add(metric)
            status_drift = bool(campaign.desired_status and campaign.real_status and campaign.desired_status.upper() != campaign.real_status.upper())
            budget_drift = bool(campaign.desired_budget and campaign.real_budget and abs(float(campaign.desired_budget) - float(campaign.real_budget)) >= 0.01)
            campaign.budget_drift_detected = budget_drift
            drift = status_drift or budget_drift
            if drift:
                drift_count += 1
                if status_drift:
                    campaign.last_state_sync_reason = "Drift detectado: estado desejado difere do estado real da Meta."
                    drift_action = "pause_campaign" if campaign.desired_status.upper() == "PAUSED" else "notify_only"
                    drift_reason = "DRIFT_DETECTED"
                    drift_target = "campaign"
                    new_budget = None
                    drift_reasoning = (
                        f"Drift detectado: desired_status={campaign.desired_status} "
                        f"real_status={campaign.real_status}. Ação exige aprovação humana."
                    )
                else:
                    campaign.last_state_sync_reason = "Drift de orçamento detectado: orçamento desejado difere do orçamento real da Meta."
                    drift_action = "scale_budget" if campaign.desired_budget > campaign.real_budget else "decrease_bid"
                    drift_reason = "BUDGET_DRIFT_DETECTED"
                    drift_target = "adset"
                    new_budget = campaign.desired_budget
                    drift_reasoning = (
                        f"Drift de orçamento detectado: desired_budget=R$ {campaign.desired_budget:.2f} "
                        f"real_budget=R$ {campaign.real_budget:.2f}. Ação exige aprovação humana."
                    )
                self._open_ticket(campaign, "yellow", drift_reason, drift_action, campaign.last_state_sync_reason)
                self._create_pending_meta_action(
                    campaign=campaign,
                    action=drift_action,
                    reason=drift_reason,
                    reasoning=drift_reasoning,
                    target=drift_target,
                    new_daily_budget_brl=new_budget,
                )
                decision_repo.create(DecisionLogCreate(
                    campaign_id=campaign.meta_campaign_id,
                    product_name=campaign.product_name,
                    reason_code=drift_reason,
                    metric_name="budget" if budget_drift and not status_drift else "status",
                    metric_value=campaign.real_budget if budget_drift and not status_drift else 1,
                    threshold_value=campaign.desired_budget if budget_drift and not status_drift else 0,
                    severity="warning",
                    tag_label="Atenção necessária",
                    action_taken=drift_action,
                    reasoning=campaign.last_state_sync_reason + " [DRY-RUN] Would create decision action; no actual write performed to Meta API.",
                    metadata_json=self._metrics_metadata(campaign, metric, extra={
                        "reason": drift_reason,
                        "dry_run": dry_run or self.meta_client.dry_run,
                        "would_action": drift_action,
                        "desired_budget": campaign.desired_budget,
                        "real_budget": campaign.real_budget,
                        "currency": campaign.currency_code,
                    }),
                ))
            else:
                campaign.last_state_sync_reason = "Estado sincronizado com a Meta."

            over_budget = bool(campaign.daily_budget and campaign.spend_today > campaign.daily_budget)
            last_decision = "SPEND_LIMIT_EXCEEDED" if over_budget else ("DRIFT_DETECTED" if drift else "SYNC_OK")
            if over_budget:
                self._open_ticket(campaign, "red", "SPEND_LIMIT_EXCEEDED", "pause_campaign", f"Gasto R${campaign.spend_today:.2f} acima do limite diário R${campaign.daily_budget:.2f}. Gere aprovação antes de executar ação real.")
                self._create_pending_meta_action(
                    campaign=campaign,
                    action="pause_campaign",
                    reason="SPEND_LIMIT_EXCEEDED",
                    reasoning=f"Gasto R${campaign.spend_today:.2f} acima do limite diário R${campaign.daily_budget:.2f}. Pausa sugerida; execução depende de aprovação humana.",
                    target="campaign",
                )
            items.append(MetaCampaignSyncItem(
                campaign_pk=campaign.id,
                internal_campaign_id=campaign.internal_campaign_id,
                meta_campaign_id=campaign.meta_campaign_id,
                name=campaign.product_name,
                real_status=campaign.real_status,
                desired_status=campaign.desired_status,
                spend_today=campaign.spend_today,
                daily_budget=campaign.daily_budget,
                desired_budget=campaign.desired_budget,
                real_budget=campaign.real_budget,
                budget_drift_detected=campaign.budget_drift_detected,
                drift_detected=drift,
                last_decision=last_decision,
            ))
        self.db.commit()
        return MetaCampaignSyncResponse(
            processed=len(rows),
            created=created,
            updated=updated,
            drift_detected=drift_count,
            dry_run=dry_run or self.meta_client.dry_run,
            items=items,
        )


    def run_decision_loop(self, dry_run: bool = True, meta_cpa_ideal: float | None = None, test_budget_brl: float | None = None, scale_budget_brl: float | None = None, limit: int = 50) -> DecisionLoopResponse:
        """Execute the AI Agency Operator optimization loop.

        Safe by default: dry_run=True. It reads active campaigns, fetches Meta
        spend when credentials allow it, falls back to latest local metrics,
        applies the budget/CPA rules and writes every decision to the timeline.
        """
        test_budget = test_budget_brl if test_budget_brl is not None else self.settings.test_budget_brl
        scale_budget = scale_budget_brl if scale_budget_brl is not None else self.settings.scale_budget_brl

        campaigns = (
            self.db.query(Campaign)
            .filter(Campaign.status.in_(["ACTIVE", "active"]))
            .order_by(desc(Campaign.updated_at))
            .limit(limit)
            .all()
        )
        results: list[DecisionLoopActionResponse] = []
        actions_taken = 0
        decision_repo = DecisionLogRepository(self.db)

        for campaign in campaigns:
            latest = (
                self.db.query(CampaignMetric)
                .filter(CampaignMetric.campaign_id == campaign.id)
                .order_by(desc(CampaignMetric.created_at))
                .first()
            )
            spend_real = self._campaign_spend_from_meta_or_local(campaign, latest)
            cpa = latest.cost_per_purchase if latest else 0.0
            target_cpa = meta_cpa_ideal if meta_cpa_ideal is not None else campaign.target_cpa
            action = "monitor"
            reason_code = "STABLE_MONITORING"
            reasoning = "Campanha ativa dentro dos limites. O agente continua monitorando."
            meta_response: dict = {"status": "monitor"}
            executed = False

            if campaign.daily_budget > 0 and spend_real > campaign.daily_budget:
                action = "pause_campaign"
                reason_code = "PAUSADA_POR_ESTOURO_ORCAMENTO"
                reasoning = (
                    f"Gasto real R${spend_real:.2f} ultrapassou orçamento diário R${campaign.daily_budget:.2f}. "
                    "Pausar evita vazamento de verba."
                )
                pending = self._create_pending_meta_action(
                    campaign=campaign,
                    action="pause_campaign",
                    reason=reason_code,
                    reasoning=reasoning,
                    target="campaign",
                )
                meta_response = {
                    "status": "pending_approval",
                    "dry_run": True,
                    "action_id": pending.id,
                    "message": "Ação criada como rascunho; nenhuma escrita foi enviada à Meta.",
                }
                executed = False
                self._open_ticket(campaign, "red", reason_code, action, reasoning)

            elif target_cpa and latest and latest.purchases > 0 and cpa > target_cpa:
                action = "decrease_bid"
                reason_code = "AJUSTE_DE_BID_AUTOMATICO"
                reduced_budget = max(1.0, campaign.daily_budget * 0.8) if campaign.daily_budget else None
                reasoning = (
                    f"CPA R${cpa:.2f} está acima da meta R${target_cpa:.2f}. "
                    "O agente reduz orçamento/bid do conjunto em 20% para controlar prejuízo."
                )
                pending = self._create_pending_meta_action(
                    campaign=campaign,
                    action="decrease_bid",
                    reason=reason_code,
                    reasoning=reasoning,
                    target="adset",
                    new_daily_budget_brl=reduced_budget,
                )
                meta_response = {
                    "status": "pending_approval",
                    "dry_run": True,
                    "action_id": pending.id,
                    "message": "Ajuste criado como rascunho; nenhuma escrita foi enviada à Meta.",
                }
                executed = False
                self._open_ticket(campaign, "yellow", reason_code, action, reasoning)

            elif latest and latest.ctr >= self.settings.scale_min_ctr and self._desired_budget(campaign) <= test_budget and campaign.meta_adset_id:
                financial_context = self._financial_context(campaign, latest)
                roas_real_brl = float(financial_context.get("calculated_roas_brl") or 0)
                fx_validated = bool(financial_context.get("fx_validated"))
                if not fx_validated:
                    action = "monitor"
                    reason_code = "FX_RATE_MISSING_BLOCK_SCALE"
                    reasoning = (
                        "Ação pendente bloqueada: falha na cotação cambial. "
                        "Não vou sugerir escala de R$ 25 para R$ 50 sem validar receita em EUR/USD e câmbio em BRL."
                    )
                    meta_response = {
                        "status": "blocked",
                        "dry_run": True,
                        "reason": reason_code,
                        "message": "Câmbio ausente ou não validado; escala bloqueada por governança financeira.",
                    }
                    self._open_ticket(campaign, "yellow", reason_code, "monitor", reasoning)
                elif roas_real_brl >= self.settings.scale_min_roas and (not target_cpa or not latest.purchases or cpa <= target_cpa):
                    action = "scale_budget"
                    reason_code = "SCALE_BUDGET_TO_50_BRL"
                    campaign.desired_budget = scale_budget
                    campaign.daily_budget = scale_budget
                    reasoning = (
                        f"Performance validada: CTR {latest.ctr:.2f}% acima do mínimo {self.settings.scale_min_ctr:.2f}%, "
                        f"ROAS unificado BRL / ROAS real em BRL {roas_real_brl:.2f} calculado com receita {financial_context.get('currency_revenue') or financial_context.get('revenue_currency')} convertida para BRL, "
                        f"CPA R${cpa:.2f} dentro da meta R${target_cpa or 0:.2f}. "
                        f"Sugestão: escalar orçamento de R$ {test_budget:.2f} para R$ {scale_budget:.2f}."
                    )
                    pending = self._create_pending_meta_action(
                        campaign=campaign,
                        action="scale_budget",
                        reason=reason_code,
                        reasoning=reasoning,
                        target="adset",
                        new_daily_budget_brl=scale_budget,
                    )
                    meta_response = {
                        "status": "pending_approval",
                        "dry_run": True,
                        "action_id": pending.id,
                        "message": "Escala criada como rascunho; nenhuma escrita foi enviada à Meta.",
                    }
                    executed = False
                    self._open_ticket(campaign, "green", reason_code, action, reasoning)
                else:
                    action = "monitor"
                    reason_code = "ROAS_REAL_BRL_BELOW_SCALE_MIN"
                    reasoning = (
                        f"CTR está bom, mas ROAS real em BRL {roas_real_brl:.2f} ainda não atingiu o mínimo "
                        f"{self.settings.scale_min_roas:.2f}. Mantendo orçamento em R$ {self._desired_budget(campaign):.2f}."
                    )
                    meta_response = {"status": "monitor", "dry_run": dry_run, "reason": reason_code}
                    self._open_ticket(campaign, "info", reason_code, "monitor", reasoning)

            decision_repo.create(DecisionLogCreate(
                campaign_id=campaign.meta_campaign_id or campaign.internal_campaign_id,
                product_name=campaign.product_name or campaign.internal_campaign_id,
                reason_code=reason_code,
                metric_name="spend_today" if reason_code == "PAUSADA_POR_ESTOURO_ORCAMENTO" else ("daily_budget" if reason_code == "SCALE_BUDGET_TO_50_BRL" else "cost_per_purchase"),
                metric_value=spend_real if reason_code == "PAUSADA_POR_ESTOURO_ORCAMENTO" else (scale_budget if reason_code == "SCALE_BUDGET_TO_50_BRL" else cpa),
                threshold_value=campaign.daily_budget if reason_code == "PAUSADA_POR_ESTOURO_ORCAMENTO" else (test_budget if reason_code == "SCALE_BUDGET_TO_50_BRL" else (target_cpa or 0)),
                severity="danger" if action == "pause_campaign" else ("success" if action == "scale_budget" else ("warning" if action == "decrease_bid" else "info")),
                tag_label="Atenção urgente" if action == "pause_campaign" else ("Escala sugerida" if action == "scale_budget" else ("Ajuste automático" if action == "decrease_bid" else "Monitoramento")),
                action_taken=action,
                reasoning=reasoning,
                metadata_json=self._metrics_metadata(campaign, latest, extra={
                    "reason_code": reason_code,
                    "action": action,
                    "dry_run": dry_run,
                    "meta_response": meta_response,
                    "meta_cpa_ideal": meta_cpa_ideal,
                    "currency": self.settings.currency_code,
                    "test_budget_brl": test_budget,
                    "scale_budget_brl": scale_budget,
                    "financial_context": self._financial_context(campaign, latest),
                }),
            ))
            if executed:
                actions_taken += 1
            results.append(DecisionLoopActionResponse(
                campaign_pk=campaign.id,
                internal_campaign_id=campaign.internal_campaign_id,
                meta_campaign_id=campaign.meta_campaign_id,
                meta_adset_id=campaign.meta_adset_id,
                spend_real=spend_real,
                daily_budget=campaign.daily_budget,
                desired_budget=campaign.desired_budget,
                real_budget=campaign.real_budget,
                cpa=cpa,
                target_cpa=target_cpa or 0,
                action=action,
                executed=executed,
                dry_run=bool(meta_response.get("dry_run", dry_run)),
                reason_code=reason_code,
                reasoning=reasoning,
                meta_response=meta_response,
            ))

        self.db.commit()
        return DecisionLoopResponse(processed=len(campaigns), actions_taken=actions_taken, dry_run=dry_run, results=results)

    def _evaluate_scaling_rule(self, campaign: Campaign, rule: ScalingRule, dry_run: bool = True) -> IntelligentScalingResponse:
        latest_financial = self._latest_financial_metric(campaign)
        latest_metric = (
            self.db.query(CampaignMetric)
            .filter(CampaignMetric.campaign_id == campaign.id)
            .order_by(desc(CampaignMetric.created_at))
            .first()
        )
        roas = float(latest_financial.calculated_roas_brl if latest_financial else (latest_metric.unified_roas_brl if latest_metric else 0))
        sales_volume = int((latest_metric.purchases if latest_metric else 0) or 0)
        manual_sales = (
            self.db.query(ManualRevenueEntry)
            .filter(ManualRevenueEntry.campaign_id == campaign.id)
            .order_by(desc(ManualRevenueEntry.created_at))
            .all()
        )
        if manual_sales:
            sales_volume = max(sales_volume, sum(row.sales_count for row in manual_sales))
        current_budget = float(campaign.daily_budget or campaign.desired_budget or self.settings.test_budget_brl)

        # Cooldown protection: never suggest scale during the learning window.
        if rule.last_scale_date:
            elapsed = datetime.now(UTC) - rule.last_scale_date.replace(tzinfo=UTC) if rule.last_scale_date.tzinfo is None else datetime.now(UTC) - rule.last_scale_date
            if elapsed < timedelta(days=rule.cooldown_days):
                return self._scaling_result(
                    campaign, current_budget, current_budget, 0, roas, sales_volume,
                    "HOLD", "SCALE_COOLDOWN_ACTIVE",
                    f"Aguardando fim da janela de aprendizado de {rule.cooldown_days} dias antes de novo aporte.", None,
                )

        if sales_volume < rule.min_sales_volume:
            return self._scaling_result(
                campaign, current_budget, current_budget, 0, roas, sales_volume,
                "HOLD", "INSUFFICIENT_SALES_VOLUME",
                f"Volume de vendas {sales_volume} abaixo do mínimo {rule.min_sales_volume}; escala bloqueada.", None,
            )
        if latest_metric and rule.max_cpa_brl and latest_metric.cost_per_purchase > rule.max_cpa_brl:
            return self._scaling_result(
                campaign, current_budget, current_budget, 0, roas, sales_volume,
                "HOLD", "CPA_ABOVE_SCALE_LIMIT",
                f"CPA R$ {latest_metric.cost_per_purchase:.2f} acima do limite R$ {rule.max_cpa_brl:.2f}; não escalar.", None,
            )
        if latest_metric and rule.min_ctr and latest_metric.ctr < rule.min_ctr:
            return self._scaling_result(
                campaign, current_budget, current_budget, 0, roas, sales_volume,
                "HOLD", "CTR_BELOW_SCALE_LIMIT",
                f"CTR {latest_metric.ctr:.2f}% abaixo do mínimo {rule.min_ctr:.2f}%; possível fadiga criativa.", None,
            )
        if not latest_financial or not latest_financial.fx_validated:
            return self._scaling_result(
                campaign, current_budget, current_budget, 0, roas, sales_volume,
                "HOLD", "FX_RATE_MISSING_BLOCK_SCALE",
                "Câmbio/receita não validado; escala bloqueada por governança financeira.", None,
            )
        if roas < rule.min_roas_threshold:
            return self._scaling_result(
                campaign, current_budget, current_budget, 0, roas, sales_volume,
                "HOLD", "ROAS_BELOW_SCALE_THRESHOLD",
                f"ROAS real em BRL {roas:.2f} abaixo da meta {rule.min_roas_threshold:.2f}.", None,
            )

        increment = rule.increment_percentage
        if roas < rule.excellent_roas_threshold:
            increment = rule.standard_increment_percentage
        new_budget = round(current_budget * (1 + (increment / 100)), 2)
        if new_budget > rule.max_budget_cap:
            new_budget = float(rule.max_budget_cap)
        if new_budget <= current_budget:
            return self._scaling_result(
                campaign, current_budget, current_budget, increment, roas, sales_volume,
                "HOLD", "MAX_BUDGET_CAP_REACHED",
                f"Teto de orçamento R$ {rule.max_budget_cap:.2f} já foi atingido; escala bloqueada.", None,
            )

        existing = (
            self.db.query(MetaActionRequest)
            .filter(
                MetaActionRequest.campaign_id == campaign.id,
                MetaActionRequest.action == "scale_budget",
                MetaActionRequest.status.in_(["pending_approval", "approved"]),
            )
            .order_by(desc(MetaActionRequest.created_at))
            .first()
        )
        if existing:
            return self._scaling_result(
                campaign, current_budget, new_budget, increment, roas, sales_volume,
                "SCALE_BUDGET", "SCALE_ALREADY_PENDING",
                "Já existe uma sugestão de escala pendente/aprovada; aguardando resolução antes de criar outra.", existing.id,
            )

        reasoning = (
            f"Performance validada por regra de escala: ROAS real em BRL {roas:.2f}, "
            f"volume de vendas {sales_volume}. Sugestão: aumentar orçamento de R$ {current_budget:.2f} "
            f"para R$ {new_budget:.2f} (+{increment}%)."
        )
        pending = self._create_pending_meta_action(
            campaign=campaign,
            action="scale_budget",
            reason="PERFORMANCE_VALIDATED_SCALE",
            reasoning=reasoning,
            target="adset",
            new_daily_budget_brl=new_budget,
        )
        self._open_ticket(campaign, "green", "PERFORMANCE_VALIDATED_SCALE", "scale_budget", reasoning)
        DecisionLogRepository(self.db).create(DecisionLogCreate(
            campaign_id=campaign.meta_campaign_id or campaign.internal_campaign_id,
            product_name=campaign.product_name or campaign.internal_campaign_id,
            reason_code="PERFORMANCE_VALIDATED_SCALE",
            metric_name="roas_final_brl",
            metric_value=roas,
            threshold_value=rule.min_roas_threshold,
            severity="success",
            tag_label="Escala sugerida",
            action_taken="scale_budget",
            reasoning=reasoning,
            metadata_json=self._metrics_metadata(campaign, latest_metric, extra={
                "scaling_rule_id": rule.id,
                "current_budget_brl": current_budget,
                "proposed_budget_brl": new_budget,
                "increment_percentage": increment,
                "cooldown_days": rule.cooldown_days,
                "sales_volume": sales_volume,
                "financial_metric_id": latest_financial.id if latest_financial else None,
                "dry_run": dry_run,
                "action_id": pending.id,
            }),
        ))
        campaign.desired_budget = new_budget
        campaign.budget_drift_detected = bool(abs(float(campaign.real_budget or 0) - new_budget) >= 0.01)
        return self._scaling_result(
            campaign, current_budget, new_budget, increment, roas, sales_volume,
            "SCALE_BUDGET", "PERFORMANCE_VALIDATED_SCALE", reasoning, pending.id,
        )

    def _scaling_result(
        self,
        campaign: Campaign,
        current_budget: float,
        proposed_budget: float,
        increment: int,
        roas: float,
        sales_volume: int,
        action: str,
        reason_code: str,
        reasoning: str,
        action_id: int | None,
    ) -> IntelligentScalingResponse:
        return IntelligentScalingResponse(
            campaign_pk=campaign.id,
            internal_campaign_id=campaign.internal_campaign_id,
            meta_campaign_id=campaign.meta_campaign_id,
            current_budget_brl=current_budget,
            proposed_budget_brl=proposed_budget,
            increment_percentage=increment,
            roas_brl=roas,
            sales_volume=sales_volume,
            action=action,
            reason_code=reason_code,
            reasoning=reasoning,
            action_id=action_id,
            status="pending" if action_id else "blocked" if action == "HOLD" else "ok",
        )

    def _latest_financial_metric(self, campaign: Campaign) -> FinancialMetric | None:
        return (
            self.db.query(FinancialMetric)
            .filter(FinancialMetric.campaign_id == campaign.id)
            .order_by(desc(FinancialMetric.created_at))
            .first()
        )

    def _financial_context(self, campaign: Campaign, latest: CampaignMetric | None = None) -> dict:
        financial = self._latest_financial_metric(campaign)
        if financial:
            return {
                "currency_cost": "BRL",
                "currency_revenue": financial.revenue_currency,
                "spend_brl": financial.spend_brl,
                "revenue_amount": financial.revenue_amount,
                "exchange_rate_snapshot": financial.exchange_rate,
                "exchange_rate_source": financial.exchange_rate_source,
                "fx_validated": financial.fx_validated,
                "revenue_brl": financial.revenue_brl,
                "calculated_roas_brl": financial.calculated_roas_brl,
                "financial_metric_id": financial.id,
            }
        if latest:
            return {
                "currency_cost": "BRL",
                "currency_revenue": latest.revenue_currency,
                "revenue_currency": latest.revenue_currency,
                "spend_brl": latest.spend,
                "revenue_amount": latest.revenue_amount,
                "exchange_rate_snapshot": latest.exchange_rate_to_brl,
                "exchange_rate_source": "metric_or_env",
                "fx_validated": bool(latest.revenue_amount > 0 and latest.exchange_rate_to_brl > 0),
                "revenue_brl": latest.revenue_brl,
                "calculated_roas_brl": latest.unified_roas_brl,
                "financial_metric_id": None,
            }
        return {
            "currency_cost": "BRL",
            "currency_revenue": campaign.currency_sales,
            "spend_brl": campaign.spend_today,
            "revenue_amount": 0,
            "exchange_rate_snapshot": 0,
            "exchange_rate_source": "missing",
            "fx_validated": False,
            "revenue_brl": 0,
            "calculated_roas_brl": 0,
            "financial_metric_id": None,
        }

    def _campaign_spend_from_meta_or_local(self, campaign: Campaign, latest: CampaignMetric | None) -> float:
        if campaign.meta_campaign_id:
            try:
                meta_spend = self.meta_client.get_campaign_spend(campaign.meta_campaign_id)
                if meta_spend > 0:
                    campaign.spend_today = meta_spend
                    return meta_spend
            except MetaMarketingError:
                pass
        if latest and latest.spend > 0:
            campaign.spend_today = latest.spend
            return latest.spend
        return campaign.spend_today or 0.0

    def _apply_loop_action(self, action: str, campaign: Campaign, new_daily_budget_brl: float | None, dry_run: bool) -> tuple[dict, bool]:
        if action in {"decrease_bid", "scale_budget"} and not campaign.meta_adset_id:
            return ({
                "status": "blocked",
                "reason": "meta_adset_id ausente; não consigo ajustar bid/orçamento do conjunto com segurança.",
                "dry_run": True,
            }, False)
        try:
            response = self.meta_client.apply_campaign_action(
                action=action,
                campaign_id=campaign.meta_campaign_id or campaign.internal_campaign_id,
                adset_id=campaign.meta_adset_id or None,
                target="adset" if action in {"decrease_bid", "scale_budget"} else "campaign",
                new_daily_budget_brl=new_daily_budget_brl,
                dry_run=dry_run,
            )
            return response, not response.get("dry_run", True) and response.get("status") == "executed"
        except MetaMarketingError as exc:
            return ({"status": "meta_error", "message": str(exc), "dry_run": True}, False)

    def _find_campaign(self, internal_campaign_id: str | None, meta_campaign_id: str | None) -> Campaign:
        query = self.db.query(Campaign)
        campaign = None
        if internal_campaign_id:
            campaign = query.filter(Campaign.internal_campaign_id == internal_campaign_id).first()
        if not campaign and meta_campaign_id:
            campaign = query.filter(Campaign.meta_campaign_id == meta_campaign_id).first()
        if not campaign:
            raise ValueError("Campanha não encontrada. Registre internal_campaign_id/meta_campaign_id antes de enviar métricas.")
        return campaign

    def _benchmark_ctr(self, niche: str | None, geo: str | None) -> float | None:
        query = self.db.query(AdLibraryBenchmark)
        if niche:
            query = query.filter(AdLibraryBenchmark.niche.ilike(f"%{niche}%"))
        if geo:
            query = query.filter(AdLibraryBenchmark.geo.ilike(f"%{geo}%"))
        row = query.order_by(desc(AdLibraryBenchmark.estimated_strength_score), desc(AdLibraryBenchmark.days_active)).first()
        return row.benchmark_ctr if row else None

    def _open_ticket(self, campaign: Campaign, severity: str, reason_code: str, action: str, reasoning: str) -> PerformanceTicket:
        ticket = PerformanceTicket(campaign_id=campaign.id, severity=severity, reason_code=reason_code, action_recommended=action, reasoning=reasoning, status="open")
        self.db.add(ticket)
        return ticket

    def _build_reasoning(self, latest: CampaignMetric, campaign: Campaign, benchmark_ctr: float | None, actions: list[str]) -> str:
        benchmark_txt = f" benchmark CTR {benchmark_ctr:.2f}%" if benchmark_ctr is not None else " sem benchmark externo ainda"
        return (
            f"Analisei {campaign.strategy_version} com CTR {latest.ctr:.2f}%, ROAS {latest.roas:.2f}, "
            f"CPA R${latest.cost_per_purchase:.2f}, Connect Rate {latest.connect_rate:.1f}% e{benchmark_txt}. "
            f"Ações recomendadas: {', '.join(dict.fromkeys(actions))}."
        )

    def _exchange_rate_to_brl(self, currency: str | None) -> float:
        code = (currency or self.settings.currency_sales or "BRL").upper()
        if code == "BRL":
            return 1.0
        if code == "USD":
            return float(self.settings.exchange_rate_usd_to_brl)
        if code == "EUR":
            return float(self.settings.exchange_rate_eur_to_brl)
        return 1.0

    def _desired_budget(self, campaign: Campaign) -> float:
        return float(campaign.desired_budget or campaign.daily_budget or self.settings.test_budget_brl)

    def _campaign_response(self, campaign: Campaign) -> CampaignResponse:
        return CampaignResponse(
            id=campaign.id,
            internal_campaign_id=campaign.internal_campaign_id,
            meta_campaign_id=campaign.meta_campaign_id,
            meta_adset_id=campaign.meta_adset_id,
            product_id=campaign.product_id,
            product_name=campaign.product_name,
            strategy_version=campaign.strategy_version,
            status=campaign.status,
            desired_status=campaign.desired_status,
            real_status=campaign.real_status,
            last_state_sync_reason=campaign.last_state_sync_reason,
            daily_budget=campaign.daily_budget,
            spend_today=campaign.spend_today,
            desired_budget=campaign.desired_budget,
            real_budget=campaign.real_budget,
            budget_drift_detected=campaign.budget_drift_detected,
            currency_code=campaign.currency_code,
            currency_ad_account=campaign.currency_ad_account,
            currency_sales=campaign.currency_sales,
            target_cpa=campaign.target_cpa,
            target_roas=campaign.target_roas,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )

    def _scaling_rule_response(self, row: ScalingRule, payload: ScalingRuleCreateRequest | None = None) -> ScalingRuleResponse:
        return ScalingRuleResponse(
            id=row.id,
            campaign_id=row.campaign_id,
            internal_campaign_id=payload.internal_campaign_id if payload else None,
            meta_campaign_id=row.meta_campaign_id,
            min_roas_threshold=row.min_roas_threshold,
            excellent_roas_threshold=row.excellent_roas_threshold,
            standard_increment_percentage=row.standard_increment_percentage,
            increment_percentage=row.increment_percentage,
            max_budget_cap=row.max_budget_cap,
            cooldown_days=row.cooldown_days,
            last_scale_date=row.last_scale_date,
            min_sales_volume=row.min_sales_volume,
            max_cpa_brl=row.max_cpa_brl,
            min_ctr=row.min_ctr,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _manual_revenue_response(self, row: ManualRevenueEntry, payload: ManualRevenueEntryCreateRequest | None = None) -> ManualRevenueEntryResponse:
        return ManualRevenueEntryResponse(
            id=row.id,
            campaign_id=row.campaign_id,
            internal_campaign_id=payload.internal_campaign_id if payload else None,
            meta_campaign_id=row.meta_campaign_id,
            revenue_amount=row.revenue_amount,
            currency=row.currency,
            exchange_rate_to_brl=row.exchange_rate_to_brl,
            sales_count=row.sales_count,
            notes=row.notes,
            created_by=row.created_by,
            revenue_brl=row.revenue_brl,
            date_reference=row.date_reference,
            created_at=row.created_at,
        )

    def _financial_metric_response(self, metric: FinancialMetric, payload: FinancialMetricCreateRequest | None = None) -> FinancialMetricResponse:
        return FinancialMetricResponse(
            id=metric.id,
            campaign_id=metric.campaign_id,
            internal_campaign_id=payload.internal_campaign_id if payload else None,
            meta_campaign_id=payload.meta_campaign_id if payload else None,
            spend_brl=metric.spend_brl,
            revenue_amount=metric.revenue_amount,
            revenue_currency=metric.revenue_currency,
            exchange_rate=metric.exchange_rate,
            exchange_rate_source=metric.exchange_rate_source,
            raw_payload=json.loads(metric.raw_payload_json or "{}"),
            revenue_brl=metric.revenue_brl,
            calculated_roas_brl=metric.calculated_roas_brl,
            fx_validated=metric.fx_validated,
            date=metric.date,
            created_at=metric.created_at,
        )

    def _metric_response(self, metric: CampaignMetric, payload: CampaignMetricCreateRequest | None = None) -> CampaignMetricResponse:
        return CampaignMetricResponse(
            id=metric.id,
            campaign_id=metric.campaign_id,
            internal_campaign_id=payload.internal_campaign_id if payload else None,
            meta_campaign_id=payload.meta_campaign_id if payload else None,
            ctr=metric.ctr,
            cpc=metric.cpc,
            cpm=metric.cpm,
            spend=metric.spend,
            purchases=metric.purchases,
            cost_per_purchase=metric.cost_per_purchase,
            roas=metric.roas,
            revenue_amount=metric.revenue_amount,
            revenue_currency=metric.revenue_currency,
            exchange_rate_to_brl=metric.exchange_rate_to_brl,
            revenue_brl=metric.revenue_brl,
            unified_roas_brl=metric.unified_roas_brl,
            connect_rate=metric.connect_rate,
            checkout_rate=metric.checkout_rate,
            capi_status=metric.capi_status,
            source=metric.source,
            date=metric.date,
            created_at=metric.created_at,
        )

    def _ticket_response(self, ticket: PerformanceTicket) -> PerformanceTicketResponse:
        return PerformanceTicketResponse(
            id=ticket.id,
            campaign_id=ticket.campaign_id,
            severity=ticket.severity,
            reason_code=ticket.reason_code,
            action_recommended=ticket.action_recommended,
            reasoning=ticket.reasoning,
            status=ticket.status,
            created_at=ticket.created_at,
        )


    def _metrics_metadata(self, campaign: Campaign, latest: CampaignMetric | None = None, extra: dict | None = None) -> str:
        payload = {
            "campaign_pk": campaign.id,
            "internal_campaign_id": campaign.internal_campaign_id,
            "meta_campaign_id": campaign.meta_campaign_id,
            "meta_adset_id": campaign.meta_adset_id,
            "strategy_version": campaign.strategy_version,
            "desired_status": campaign.desired_status,
            "real_status": campaign.real_status,
            "daily_budget": campaign.daily_budget,
            "spend_today": campaign.spend_today,
            "desired_budget": campaign.desired_budget,
            "real_budget": campaign.real_budget,
            "budget_drift_detected": campaign.budget_drift_detected,
            "currency": campaign.