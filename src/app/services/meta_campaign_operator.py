from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.integrations.affiliate_provider import AffiliateProvider
from app.integrations.meta_marketing import MetaMarketingClient, MetaMarketingError
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.decision_feed_store import DecisionFeedStore
from app.services.observability import audit_event, log_event
from app.schemas.affiliate import AffiliateReplaceRequest
from app.schemas.facebook_marketing import CampaignPlanItem
from app.schemas.meta_operator import (
    MetaOperatorCampaignResult,
    MetaOperatorGuardrail,
    MetaOperatorLaunchRequest,
    MetaOperatorLaunchResponse,
    MetaOperatorPayloadPreview,
    MetaOperatorRollbackRequest,
    MetaOperatorRollbackResponse,
    MetaOperatorStatusResponse,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / "logs"
OPERATOR_LOG = LOG_DIR / "meta_campaign_operator.log"
_LOG_LOCK = threading.Lock()
META_ENVIRONMENTS = {"sandbox", "test_account", "production"}


GEO_PRESETS: dict[str, dict[str, Any]] = {
    "LATAM_ESP": {
        "label": "Países de língua espanhola LATAM",
        "countries": ["AR", "CL", "CO", "PE", "MX", "EC"],
        "language": "Spanish_All",
        "currency_cluster": "LATAM",
    },
    "USD_TIER1": {
        "label": "Moeda forte dólar",
        "countries": ["US", "CA", "AU", "NZ"],
        "language": "English_All",
        "currency_cluster": "USD",
    },
    "EURO_TIER": {
        "label": "Moeda forte euro",
        "countries": ["DE", "FR", "ES", "IT", "NL", "IE", "PT"],
        "language": "English_All",
        "currency_cluster": "EUR",
    },
    "BRASIL": {
        "label": "Brasil manual",
        "countries": ["BR"],
        "language": "Portuguese_All",
        "currency_cluster": "BRL",
    },
}


class MetaCampaignOperator:
    """Camada oficial de execução do projeto para V3: 1 campanha por criativo.

    Guardrails principais:
    - dry-run por padrão;
    - publicação real só com META_AUTOPUBLISH=true e META_DRY_RUN=false;
    - ACTIVE launch só com META_ALLOW_ACTIVE_LAUNCH=true;
    - usa presets de GEO/idioma para evitar mistura de clusters.
    """

    def __init__(self, meta_client: MetaMarketingClient | None = None, affiliate_provider: AffiliateProvider | None = None) -> None:
        self.settings = get_settings()
        self.meta_client = meta_client or MetaMarketingClient()
        self.affiliate_provider = affiliate_provider or AffiliateProvider()

    def status(self) -> MetaOperatorStatusResponse:
        meta_env = self._meta_environment()
        return MetaOperatorStatusResponse(
            enabled=self.settings.meta_operator_enabled,
            dry_run=self.meta_client.dry_run,
            autopublish_allowed=self.settings.meta_autopublish,
            active_launch_allowed=self.settings.meta_allow_active_launch,
            configured_credentials=self.meta_client.credentials.configured,
            supported_presets=GEO_PRESETS,
            production_safety={
                "meta_environment": meta_env,
                "allowed_environments": sorted(META_ENVIRONMENTS),
                "production_real_allowed": self._production_real_allowed(),
                "daily_spend_limit_brl": self.settings.meta_production_daily_spend_limit_brl,
                "manual_confirmation_required": self.settings.meta_require_manual_confirmation,
                "created_resources_log": self.settings.meta_created_resources_log,
                "rollback_endpoint": "/api/v1/campaign-operator/rollback",
            },
            required_env=[
                "META_ACCESS_TOKEN",
                "META_AD_ACCOUNT_ID",
                "META_PAGE_ID",
                "META_ENV=sandbox|test_account|production",
                "META_DRY_RUN=false",
                "META_AUTOPUBLISH=true",
                "META_ALLOW_PRODUCTION_REAL=true somente para conta principal em producao",
                "META_ALLOW_ACTIVE_LAUNCH=true somente quando quiser publicar ACTIVE",
            ],
        )

    def production_readiness(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Missao 31: valida prontidao de producao sem publicar nada."""
        payload = payload or {}
        brain = CampaignBrainAgent()
        memory = CampaignMemoryStore()
        decision_feed = DecisionFeedStore()
        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, message: str, required: bool = True) -> None:
            checks.append({
                "name": name,
                "status": "ok" if ok else "blocked" if required else "warning",
                "required": required,
                "message": message,
            })

        add("operator_enabled", bool(self.settings.meta_operator_enabled), "MetaCampaignOperator habilitado.")
        add("meta_environment", self._meta_environment() in META_ENVIRONMENTS, "META_ENV deve ser sandbox, test_account ou production.")
        add("production_unlock", self._production_real_allowed(), "META_ENV=production exige META_ALLOW_PRODUCTION_REAL=true.", required=self._meta_environment() == "production")
        add("credentials", bool(self.meta_client.credentials.configured), "Credenciais Meta completas exigidas.")
        add("dry_run_disabled", not bool(self.meta_client.dry_run), "META_DRY_RUN=false exigido para producao.")
        add("autopublish", bool(self.settings.meta_autopublish), "META_AUTOPUBLISH=true exigido para producao.")
        add("manual_confirmation", bool(payload.get("confirmed_by_user")), "Confirmacao manual explicita exigida.")
        add("rollback_policy", bool(payload.get("rollback_policy_ack")), "Politica formal de rollback precisa ser aceita.")
        add("spend_limit", float(self.settings.meta_production_daily_spend_limit_brl or 0) > 0, "Limite diario de gasto precisa estar definido.")
        add("payload_integrity", bool(payload.get("expected_payload_sha256")), "Hash do payload aprovado deve ser informado.")
        add("brain_approval", bool(payload.get("brain_approval_ack")), "Aprovacao do Brain/Brian deve ser confirmada.")

        blocked = [item for item in checks if item["status"] == "blocked"]
        review = brain.review_before_campaign({
            "product_name": str(payload.get("product_name") or "MetaCampaignOperator Producao"),
            "niche": "producao_meta_ads",
            "campaign_stage": "MISSAO_31_PRODUCTION_READINESS",
            "budget_brl": float(payload.get("daily_budget_brl") or self.settings.test_budget_brl),
            "metrics": {
                "blocked_checks": len(blocked),
                "credentials_configured": self.meta_client.credentials.configured,
                "autopublish": self.settings.meta_autopublish,
                "dry_run": self.meta_client.dry_run,
                "meta_env": self._meta_environment(),
            },
            "offer": "Readiness de producao sem publicacao real.",
        })
        decision_feed.record_brain_decision(review, context={
            "product_name": str(payload.get("product_name") or "MetaCampaignOperator Producao"),
            "niche": "producao_meta_ads",
            "campaign_stage": "MISSAO_31_PRODUCTION_READINESS",
        })

        status = "ready" if not blocked else "blocked"
        result = {
            "mission_id": "31",
            "status": status,
            "published": False,
            "would_publish": status == "ready",
            "blocked": bool(blocked),
            "blocked_checks": blocked,
            "checks": checks,
            "rollback_required": True,
            "manual_approval_required": True,
            "spend_limit_brl": self.settings.meta_production_daily_spend_limit_brl,
            "meta_environment": self._meta_environment(),
            "created_resources_log": self.settings.meta_created_resources_log,
            "rollback_endpoint": "/api/v1/campaign-operator/rollback",
            "brain_review": review,
            "next_action": "Aguardando aprovacao humana final para producao real." if status == "ready" else "Corrigir bloqueios antes de qualquer producao real.",
        }
        audit_event(
            actor="Mission31",
            action="meta_operator_production_readiness",
            resource_type="meta_campaign_operator",
            resource_id=str(payload.get("product_name") or "production"),
            status=status,
            mission_id="31",
            details={"blocked_checks": [item["name"] for item in blocked]},
        )
        log_event(
            "mission_31_production_readiness",
            status="ok" if status == "ready" else "attention",
            mission_id="31",
            details={"blocked": bool(blocked), "blocked_checks": [item["name"] for item in blocked]},
        )
        memory.remember({
            "product_name": str(payload.get("product_name") or "MetaCampaignOperator Producao"),
            "niche": "producao_meta_ads",
            "campaign_stage": "MISSAO_31_PRODUCTION_READINESS",
            "outcome": status.upper(),
            "lesson": "MetaCampaignOperator Producao exige readiness, rollback, aprovacao manual, hash de payload e Brain antes de publicar.",
            "learning": "Mesmo com codigo pronto, producao real deve permanecer bloqueada ate todos os checks ficarem ok e o usuario aprovar explicitamente.",
            "metrics": {"blocked_checks": len(blocked), "published": False, "would_publish": status == "ready"},
            "source": "MetaCampaignOperator.production_readiness",
        })
        return result

    def launch_v3(self, payload: MetaOperatorLaunchRequest) -> MetaOperatorLaunchResponse:
        started = datetime.now(UTC)
        plans = [self._build_plan(payload, creative, index) for index, creative in enumerate(payload.creatives, start=1)]
        payload_preview = self._build_payload_preview(plans)
        account_spend_today_brl = None
        effective_dry_run = payload.mode == "dry_run" or self.meta_client.dry_run or not self.settings.meta_autopublish

        if not effective_dry_run:
            try:
                account_spend_today_brl = self.meta_client.get_ad_account_spend_today_brl()
            except MetaMarketingError:
                account_spend_today_brl = None

        guardrails = self._validate_guardrails(payload, payload_preview.payload_sha256, account_spend_today_brl, effective_dry_run)
        blocked_by_guardrails = any(item.status == "blocked" for item in guardrails)

        results: list[MetaOperatorCampaignResult] = []
        published = 0
        blocked = 0

        for creative, plan in zip(payload.creatives, plans, strict=True):
            if blocked_by_guardrails:
                blocked += 1
                results.append(self._blocked_result(plan, creative.name, "Bloqueado pelos guardrails do operador."))
                continue
            if effective_dry_run:
                meta_result = self._simulate_plan(plan)
                results.append(self._result_from_meta(plan, creative.name, meta_result, forced_status="simulated"))
                continue
            try:
                meta_result = self._publish_plan(plan)
                if not meta_result.get("dry_run"):
                    published += 1
                    self._register_created_resources(plan, meta_result)
                results.append(self._result_from_meta(plan, creative.name, meta_result))
            except MetaMarketingError as exc:
                blocked += 1
                results.append(self._blocked_result(plan, creative.name, str(exc), status="meta_error"))

        response = MetaOperatorLaunchResponse(
            started_at=started,
            finished_at=datetime.now(UTC),
            mode=payload.mode,
            dry_run=effective_dry_run,
            product_name=payload.product_name,
            geo_preset=payload.geo_preset,
            language=payload.language,
            attempted=len(payload.creatives),
            published=published,
            blocked=blocked,
            guardrails=guardrails,
            payload_preview=payload_preview,
            account_spend_today_brl=account_spend_today_brl,
            results=results,
        )
        self._write_log(response.model_dump(mode="json"))
        return response

    def rollback_policy(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Formaliza a politica de rollback sem executar acao real na Meta."""
        payload = payload or {}
        records = self._read_created_resources()
        resources_log = Path(self.settings.meta_created_resources_log)
        requested_real_rollback = not bool(payload.get("force_dry_run", True))
        brain = CampaignBrainAgent()
        memory = CampaignMemoryStore()
        decision_feed = DecisionFeedStore()

        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, message: str, required: bool = True) -> None:
            checks.append({
                "name": name,
                "status": "ok" if ok else "blocked" if required else "warning",
                "required": required,
                "message": message,
            })

        add("created_resources_log_path", bool(str(resources_log)), "Caminho do log de recursos criados definido.")
        add("created_resources_log_readable", resources_log.exists(), "Log de recursos criados precisa existir para rollback real.", required=requested_real_rollback)
        add("dry_run_default", bool(payload.get("force_dry_run", True)), "Rollback deve nascer em dry-run por padrao.", required=False)
        add("manual_confirmation", bool(payload.get("confirmed_by_user")), "Rollback real exige confirmacao manual explicita.", required=requested_real_rollback)
        add("rollback_policy_ack", bool(payload.get("rollback_policy_ack")), "Usuario precisa aceitar a politica formal de rollback.", required=requested_real_rollback)
        add("brain_approval", bool(payload.get("brain_approval_ack")), "Brain/Brian precisam aprovar a execucao real.", required=requested_real_rollback)
        add("operator_autopublish", bool(self.settings.meta_autopublish), "Rollback real exige ambiente Meta de producao liberado.", required=requested_real_rollback)
        add("credentials", bool(self.meta_client.credentials.configured), "Credenciais Meta completas exigidas para rollback real.", required=requested_real_rollback)

        blocked = [item for item in checks if item["status"] == "blocked"]
        status = "blocked" if blocked else "ready" if requested_real_rollback else "dry_run_ready"
        review = brain.review_before_campaign({
            "product_name": str(payload.get("product_name") or "Rollback Formal Producao"),
            "niche": "rollback_meta_ads",
            "campaign_stage": "ROLLBACK_FORMAL",
            "budget_brl": 0,
            "metrics": {
                "created_resources": len(records),
                "requested_real_rollback": requested_real_rollback,
                "blocked_checks": len(blocked),
            },
            "offer": "Politica formal de rollback sem execucao real.",
        })
        decision_feed.record_brain_decision(review, context={
            "product_name": str(payload.get("product_name") or "Rollback Formal Producao"),
            "niche": "rollback_meta_ads",
            "campaign_stage": "ROLLBACK_FORMAL",
        })

        result = {
            "mission_id": "rollback-formal",
            "status": status,
            "executed": False,
            "would_execute_real_rollback": requested_real_rollback and status == "ready",
            "manual_approval_required": True,
            "rollback_endpoint": "/api/v1/campaign-operator/rollback",
            "created_resources_log": str(resources_log),
            "created_resources_count": len(records),
            "allowed_actions": ["pause", "delete"],
            "checks": checks,
            "blocked_checks": blocked,
            "brain_review": review,
            "next_action": "Executar apenas dry-run de rollback ou coletar aprovacoes para execucao assistida.",
        }
        audit_event(
            actor="RollbackFormal",
            action="meta_operator_rollback_policy",
            resource_type="meta_campaign_operator",
            resource_id=str(payload.get("product_name") or "rollback"),
            status=status,
            mission_id="rollback-formal",
            details={"blocked_checks": [item["name"] for item in blocked], "executed": False},
        )
        log_event(
            "rollback_formal_policy",
            status="ok" if status != "blocked" else "attention",
            mission_id="rollback-formal",
            details={"status": status, "created_resources": len(records), "executed": False},
        )
        memory.remember({
            "product_name": str(payload.get("product_name") or "Rollback Formal Producao"),
            "niche": "rollback_meta_ads",
            "campaign_stage": "ROLLBACK_FORMAL",
            "outcome": status.upper(),
            "lesson": "Rollback real so pode acontecer com politica aceita, confirmacao humana, Brain/Brian e credenciais revisadas.",
            "learning": "A politica formal deve ser validada antes da execucao tecnica de rollback.",
            "metrics": {"created_resources": len(records), "blocked_checks": len(blocked), "executed": False},
            "source": "MetaCampaignOperator.rollback_policy",
        })
        self._write_log({"event": "rollback_policy", **result})
        return result

    def credential_payload_review(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Revisa credenciais e payload real sem expor segredo e sem publicar."""
        payload = payload or {}
        launch_payload = payload.get("launch_payload") if isinstance(payload.get("launch_payload"), dict) else payload
        brain = CampaignBrainAgent()
        memory = CampaignMemoryStore()
        decision_feed = DecisionFeedStore()
        checks: list[dict[str, Any]] = []
        preview: dict[str, Any] | None = None
        payload_error: str | None = None

        def add(name: str, ok: bool, message: str, required: bool = True) -> None:
            checks.append({
                "name": name,
                "status": "ok" if ok else "blocked" if required else "warning",
                "required": required,
                "message": message,
            })

        token_present = bool(self.settings.meta_access_token)
        ad_account_present = bool(self.settings.meta_ad_account_id)
        page_present = bool(self.settings.meta_page_id)
        meta_env = self._meta_environment()
        add("access_token_present", token_present, "META_ACCESS_TOKEN precisa estar definido.")
        add("ad_account_present", ad_account_present, "META_AD_ACCOUNT_ID precisa estar definido.")
        add("page_present", page_present, "META_PAGE_ID precisa estar definido.")
        add("meta_environment", meta_env in META_ENVIRONMENTS, "META_ENV deve ser sandbox, test_account ou production.")
        add("production_unlock", self._production_real_allowed(), "META_ENV=production exige META_ALLOW_PRODUCTION_REAL=true.", required=meta_env == "production")
        add("dry_run_disabled", not bool(self.meta_client.dry_run), "Para producao real, dry-run precisa estar desligado.")
        add("autopublish", bool(self.settings.meta_autopublish), "META_AUTOPUBLISH=true exigido para producao real.")
        add("manual_confirmation", bool(payload.get("confirmed_by_user")), "Confirmacao humana explicita exigida.")
        add("rollback_policy_ack", bool(payload.get("rollback_policy_ack")), "Rollback formal precisa estar aceito.")
        add("brain_approval", bool(payload.get("brain_approval_ack")), "Brain/Brian precisam aprovar antes da execucao.")

        try:
            request = MetaOperatorLaunchRequest.model_validate(launch_payload)
            plans = [self._build_plan(request, creative, index) for index, creative in enumerate(request.creatives, start=1)]
            payload_preview = self._build_payload_preview(plans)
            preview = {
                "payload_sha256": payload_preview.payload_sha256,
                "campaign_count": len(payload_preview.plans),
                "product_name": request.product_name,
                "geo_preset": request.geo_preset,
                "language": request.language,
                "mode": request.mode,
            }
            add("payload_schema", True, "Payload de campanha valido.")
            add(
                "expected_payload_sha256",
                bool(payload.get("expected_payload_sha256")) and payload.get("expected_payload_sha256") == payload_preview.payload_sha256,
                "Hash aprovado precisa bater com o payload revisado.",
            )
        except ValidationError as exc:
            payload_error = exc.errors()[0].get("msg", "Payload invalido.") if exc.errors() else "Payload invalido."
            add("payload_schema", False, f"Payload invalido: {payload_error}")
            add("expected_payload_sha256", False, "Hash aprovado so pode ser validado com payload valido.")

        blocked = [item for item in checks if item["status"] == "blocked"]
        status = "ready" if not blocked else "blocked"
        review = brain.review_before_campaign({
            "product_name": str((launch_payload or {}).get("product_name") or "Revisao Credenciais Payload"),
            "niche": "credenciais_payload_meta",
            "campaign_stage": "CREDENTIAL_PAYLOAD_REVIEW",
            "budget_brl": float((launch_payload or {}).get("daily_budget_brl") or self.settings.test_budget_brl),
            "metrics": {
                "blocked_checks": len(blocked),
                "token_present": token_present,
                "payload_valid": preview is not None,
                "meta_env": meta_env,
            },
            "offer": "Revisao segura sem expor credenciais e sem publicar.",
        })
        decision_feed.record_brain_decision(review, context={
            "product_name": str((launch_payload or {}).get("product_name") or "Revisao Credenciais Payload"),
            "niche": "credenciais_payload_meta",
            "campaign_stage": "CREDENTIAL_PAYLOAD_REVIEW",
        })

        result = {
            "mission_id": "credential-payload-review",
            "status": status,
            "published": False,
            "would_publish": status == "ready",
            "secrets_redacted": True,
            "credentials": {
                "meta_environment": meta_env,
                "access_token_present": token_present,
                "ad_account_present": ad_account_present,
                "page_present": page_present,
                "instagram_actor_present": bool(self.settings.meta_instagram_actor_id),
                "pixel_present": bool(self.settings.meta_pixel_id),
            },
            "payload_preview": preview,
            "payload_error": payload_error,
            "checks": checks,
            "blocked_checks": blocked,
            "brain_review": review,
            "next_action": "Execucao assistida somente com aprovacao explicita." if status == "ready" else "Corrigir checks bloqueados antes de qualquer execucao real.",
        }
        audit_event(
            actor="CredentialPayloadReview",
            action="meta_operator_credential_payload_review",
            resource_type="meta_campaign_operator",
            resource_id=str((launch_payload or {}).get("product_name") or "credential-review"),
            status=status,
            mission_id="credential-payload-review",
            details={"blocked_checks": [item["name"] for item in blocked], "published": False},
        )
        log_event(
            "credential_payload_review",
            status="ok" if status == "ready" else "attention",
            mission_id="credential-payload-review",
            details={"blocked": bool(blocked), "published": False},
        )
        memory.remember({
            "product_name": str((launch_payload or {}).get("product_name") or "Revisao Credenciais Payload"),
            "niche": "credenciais_payload_meta",
            "campaign_stage": "CREDENTIAL_PAYLOAD_REVIEW",
            "outcome": status.upper(),
            "lesson": "Credenciais nunca devem aparecer em resposta, log ou documentacao; revisar apenas presenca e coerencia.",
            "learning": "Payload real deve gerar hash aprovado antes de qualquer execucao assistida.",
            "metrics": {"blocked_checks": len(blocked), "payload_valid": preview is not None, "published": False},
            "source": "MetaCampaignOperator.credential_payload_review",
        })
        self._write_log({"event": "credential_payload_review", **result})
        return result

    def assisted_execution_gate(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Prepara execucao assistida sem publicar e sem chamar Meta real."""
        payload = payload or {}
        required_phrase = "EU APROVO EXECUCAO REAL ASSISTIDA"
        approval_phrase_ok = str(payload.get("approval_phrase") or "").strip() == required_phrase
        credential_review = self.credential_payload_review(payload)
        rollback_review = self.rollback_policy({
            "product_name": payload.get("product_name") or "Execucao Assistida",
            "force_dry_run": True,
            "confirmed_by_user": bool(payload.get("confirmed_by_user")),
            "rollback_policy_ack": bool(payload.get("rollback_policy_ack")),
            "brain_approval_ack": bool(payload.get("brain_approval_ack")),
        })
        checks = [
            {
                "name": "meta_environment",
                "status": "ok" if self._meta_environment() in {"sandbox", "test_account"} or self._production_real_allowed() else "blocked",
                "required": True,
                "message": "Executar primeiro em sandbox/test_account; production exige META_ALLOW_PRODUCTION_REAL=true.",
            },
            {
                "name": "approval_phrase",
                "status": "ok" if approval_phrase_ok else "blocked",
                "required": True,
                "message": "Frase exata exigida: EU APROVO EXECUCAO REAL ASSISTIDA.",
            },
            {
                "name": "credential_payload_review",
                "status": "ok" if credential_review["status"] == "ready" else "blocked",
                "required": True,
                "message": "Credenciais e payload precisam estar prontos.",
            },
            {
                "name": "rollback_policy",
                "status": "ok" if rollback_review["status"] in {"dry_run_ready", "ready"} else "blocked",
                "required": True,
                "message": "Rollback formal precisa estar validado.",
            },
        ]
        blocked = [item for item in checks if item["status"] == "blocked"]
        status = "ready_for_human_execution" if not blocked else "blocked"
        result = {
            "mission_id": "assisted-execution-gate",
            "status": status,
            "published": False,
            "executed": False,
            "would_publish": status == "ready_for_human_execution",
            "requires_final_human_action": True,
            "checks": checks,
            "blocked_checks": blocked,
            "credential_review_status": credential_review["status"],
            "rollback_policy_status": rollback_review["status"],
            "payload_sha256": (credential_review.get("payload_preview") or {}).get("payload_sha256"),
            "meta_environment": self._meta_environment(),
            "next_action": "Somente o usuario pode iniciar a publicacao real apos revisar o hash e confirmar no operador." if status == "ready_for_human_execution" else "Corrigir bloqueios antes de qualquer execucao real.",
        }
        audit_event(
            actor="AssistedExecutionGate",
            action="meta_operator_assisted_execution_gate",
            resource_type="meta_campaign_operator",
            resource_id=str(payload.get("product_name") or "assisted-execution"),
            status=status,
            mission_id="assisted-execution-gate",
            details={"blocked_checks": [item["name"] for item in blocked], "published": False},
        )
        log_event(
            "assisted_execution_gate",
            status="ok" if status == "ready_for_human_execution" else "attention",
            mission_id="assisted-execution-gate",
            details={"blocked": bool(blocked), "published": False},
        )
        CampaignMemoryStore().remember({
            "product_name": str(payload.get("product_name") or "Execucao Assistida"),
            "niche": "execucao_assistida_meta",
            "campaign_stage": "ASSISTED_EXECUTION_GATE",
            "outcome": status.upper(),
            "lesson": "Execucao real assistida precisa de frase explicita, hash aprovado, rollback e revisao de credenciais.",
            "learning": "O sistema pode preparar a execucao, mas nao deve publicar automaticamente sem acao humana final.",
            "metrics": {"blocked_checks": len(blocked), "published": False, "executed": False},
            "source": "MetaCampaignOperator.assisted_execution_gate",
        })
        self._write_log({"event": "assisted_execution_gate", **result})
        return result

    def post_execution_monitor(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Monitora campanhas criadas sem executar acoes corretivas automaticas."""
        payload = payload or {}
        force_dry_run = bool(payload.get("force_dry_run", True))
        allow_real_insights = bool(payload.get("allow_real_insights", False))
        effective_dry_run = force_dry_run or self.meta_client.dry_run or not allow_real_insights
        records = self._read_created_resources()
        manual_records = payload.get("created_resources")
        if isinstance(manual_records, list):
            records = [item for item in manual_records if isinstance(item, dict)]

        brain = CampaignBrainAgent()
        memory = CampaignMemoryStore()
        decision_feed = DecisionFeedStore()
        spend_limit = float(payload.get("daily_spend_limit_brl") or self.settings.meta_production_daily_spend_limit_brl or 0)
        monitored: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []

        for record in records:
            campaign_id = str(record.get("campaign_id") or "")
            if not campaign_id:
                continue
            try:
                status_real = self.meta_client.get_campaign_status(campaign_id) if not effective_dry_run else "SIMULATED_ACTIVE"
                spend_today = self.meta_client.get_campaign_spend(campaign_id) if not effective_dry_run else float(record.get("spend_today") or 0)
            except MetaMarketingError as exc:
                status_real = "ERROR"
                spend_today = 0.0
                alerts.append({"campaign_id": campaign_id, "level": "red", "reason": "META_INSIGHTS_ERROR", "message": str(exc)})

            campaign_alerts: list[dict[str, Any]] = []
            if spend_limit > 0 and spend_today > spend_limit:
                campaign_alerts.append({
                    "level": "red",
                    "reason": "SPEND_LIMIT_EXCEEDED",
                    "recommended_action": "pause_campaign_pending_approval",
                    "message": f"Gasto R${spend_today:.2f} acima do limite R${spend_limit:.2f}.",
                })
            if status_real in {"ERROR", "UNKNOWN"}:
                campaign_alerts.append({
                    "level": "yellow",
                    "reason": "STATUS_UNKNOWN",
                    "recommended_action": "manual_review",
                    "message": "Status da campanha precisa de revisao humana.",
                })
            alerts.extend({"campaign_id": campaign_id, **alert} for alert in campaign_alerts)
            monitored.append({
                "campaign_id": campaign_id,
                "campaign_name": record.get("campaign_name"),
                "status_real": status_real,
                "spend_today_brl": spend_today,
                "alerts": campaign_alerts,
            })

        blocked_real_monitoring = not effective_dry_run and not self.meta_client.credentials.configured
        status = "blocked" if blocked_real_monitoring else "attention" if alerts else "ok"
        review = brain.review_before_campaign({
            "product_name": str(payload.get("product_name") or "Monitoramento Pos Execucao"),
            "niche": "monitoramento_meta_ads",
            "campaign_stage": "POST_EXECUTION_MONITOR",
            "budget_brl": spend_limit,
            "metrics": {
                "monitored_campaigns": len(monitored),
                "alerts": len(alerts),
                "effective_dry_run": effective_dry_run,
            },
            "offer": "Monitoramento seguro sem acoes automaticas.",
        })
        decision_feed.record_brain_decision(review, context={
            "product_name": str(payload.get("product_name") or "Monitoramento Pos Execucao"),
            "niche": "monitoramento_meta_ads",
            "campaign_stage": "POST_EXECUTION_MONITOR",
        })

        result = {
            "mission_id": "post-execution-monitor",
            "status": status,
            "dry_run": effective_dry_run,
            "executed_actions": [],
            "auto_actions_enabled": False,
            "monitored_campaigns": monitored,
            "alerts": alerts,
            "created_resources_count": len(records),
            "daily_spend_limit_brl": spend_limit,
            "brain_review": review,
            "next_action": "Aprovar acao corretiva manual se houver alerta vermelho." if alerts else "Manter monitoramento.",
        }
        audit_event(
            actor="PostExecutionMonitor",
            action="meta_operator_post_execution_monitor",
            resource_type="meta_campaign_operator",
            resource_id=str(payload.get("product_name") or "post-execution"),
            status=status,
            mission_id="post-execution-monitor",
            details={"alerts": len(alerts), "monitored_campaigns": len(monitored), "dry_run": effective_dry_run},
        )
        log_event(
            "post_execution_monitor",
            status="ok" if status == "ok" else "attention",
            mission_id="post-execution-monitor",
            details={"alerts": len(alerts), "monitored_campaigns": len(monitored), "dry_run": effective_dry_run},
        )
        memory.remember({
            "product_name": str(payload.get("product_name") or "Monitoramento Pos Execucao"),
            "niche": "monitoramento_meta_ads",
            "campaign_stage": "POST_EXECUTION_MONITOR",
            "outcome": status.upper(),
            "lesson": "Monitoramento pos-execucao deve observar gasto/status e propor acoes sem executar automaticamente.",
            "learning": "Alertas vermelhos geram recomendacao de pausa pendente de aprovacao humana.",
            "metrics": {"alerts": len(alerts), "monitored_campaigns": len(monitored), "dry_run": effective_dry_run},
            "source": "MetaCampaignOperator.post_execution_monitor",
        })
        self._write_log({"event": "post_execution_monitor", **result})
        return result

    def production_hardening_review(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Audita configuracao de producao sem alterar ambiente e sem expor segredos."""
        payload = payload or {}
        brain = CampaignBrainAgent()
        memory = CampaignMemoryStore()
        decision_feed = DecisionFeedStore()
        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, message: str, required: bool = True) -> None:
            checks.append({
                "name": name,
                "status": "ok" if ok else "blocked" if required else "warning",
                "required": required,
                "message": message,
            })

        jwt_is_default = self.settings.jwt_secret_key in {"change-me-super-secret-local-key", "change-me-local-dev-only"}
        meta_env = self._meta_environment()
        add("auth_required", bool(self.settings.auth_required), "AUTH_REQUIRED=true recomendado para producao.")
        add("jwt_secret_rotated", not jwt_is_default, "JWT_SECRET_KEY nao pode usar valor padrao em producao.")
        add("meta_environment", meta_env in META_ENVIRONMENTS, "META_ENV deve ser sandbox, test_account ou production.")
        add("production_unlock", self._production_real_allowed(), "META_ENV=production exige META_ALLOW_PRODUCTION_REAL=true.", required=meta_env == "production")
        add("meta_operator_enabled", bool(self.settings.meta_operator_enabled), "MetaCampaignOperator precisa estar habilitado.")
        add("manual_confirmation", bool(self.settings.meta_require_manual_confirmation), "Confirmacao manual deve permanecer exigida.")
        add("daily_spend_limit", float(self.settings.meta_production_daily_spend_limit_brl or 0) > 0, "Limite diario de gasto precisa estar definido.")
        add("created_resources_log", bool(self.settings.meta_created_resources_log), "Log de recursos criados precisa estar definido.")
        add("automation_level_safe", int(self.settings.automation_level or 0) <= 1, "Automacao acima de nivel 1 exige auditoria adicional.", required=False)
        add("kill_switch_reviewed", bool(self.settings.kill_switch_enabled), "Kill switch ativo e recomendado antes de producao real.", required=False)
        add("dry_run_currently_safe", bool(self.meta_client.dry_run), "Ambiente atual segue protegido em dry-run.", required=False)
        add("autopublish_currently_blocked", not bool(self.settings.meta_autopublish), "Autopublish segue bloqueado no ambiente atual.", required=False)

        blocked = [item for item in checks if item["status"] == "blocked"]
        warnings = [item for item in checks if item["status"] == "warning"]
        status = "blocked" if blocked else "ready_with_warnings" if warnings else "ready"
        review = brain.review_before_campaign({
            "product_name": str(payload.get("product_name") or "Hardening Producao"),
            "niche": "hardening_producao",
            "campaign_stage": "PRODUCTION_HARDENING",
            "budget_brl": float(self.settings.meta_production_daily_spend_limit_brl or 0),
            "metrics": {
                "blocked_checks": len(blocked),
                "warning_checks": len(warnings),
                "dry_run": self.meta_client.dry_run,
                "autopublish": self.settings.meta_autopublish,
                "meta_env": meta_env,
            },
            "offer": "Auditoria de hardening sem exposicao de segredos.",
        })
        decision_feed.record_brain_decision(review, context={
            "product_name": str(payload.get("product_name") or "Hardening Producao"),
            "niche": "hardening_producao",
            "campaign_stage": "PRODUCTION_HARDENING",
        })

        result = {
            "mission_id": "production-hardening",
            "status": status,
            "secrets_redacted": True,
            "published": False,
            "executed": False,
            "checks": checks,
            "blocked_checks": blocked,
            "warning_checks": warnings,
            "safe_runtime": {
                "dry_run": self.meta_client.dry_run,
                "meta_environment": meta_env,
                "autopublish": self.settings.meta_autopublish,
                "manual_confirmation_required": self.settings.meta_require_manual_confirmation,
                "automation_level": self.settings.automation_level,
                "kill_switch_enabled": self.settings.kill_switch_enabled,
            },
            "brain_review": review,
            "next_action": "Corrigir checks bloqueados antes de qualquer producao real." if blocked else "Revisar warnings e manter aprovacao humana final.",
        }
        audit_event(
            actor="ProductionHardening",
            action="meta_operator_production_hardening_review",
            resource_type="meta_campaign_operator",
            resource_id=str(payload.get("product_name") or "hardening"),
            status=status,
            mission_id="production-hardening",
            details={"blocked_checks": [item["name"] for item in blocked], "warnings": [item["name"] for item in warnings]},
        )
        log_event(
            "production_hardening_review",
            status="ok" if not blocked else "attention",
            mission_id="production-hardening",
            details={"blocked": len(blocked), "warnings": len(warnings)},
        )
        memory.remember({
            "product_name": str(payload.get("product_name") or "Hardening Producao"),
            "niche": "hardening_producao",
            "campaign_stage": "PRODUCTION_HARDENING",
            "outcome": status.upper(),
            "lesson": "Hardening final deve bloquear producao com auth fraco, JWT padrao ou ausencia de limites.",
            "learning": "Warnings operacionais nao publicam nada; eles orientam revisao antes da aprovacao humana final.",
            "metrics": {"blocked_checks": len(blocked), "warning_checks": len(warnings), "published": False},
            "source": "MetaCampaignOperator.production_hardening_review",
        })
        self._write_log({"event": "production_hardening_review", **result})
        return result

    def rollback_created_campaigns(self, payload: MetaOperatorRollbackRequest) -> MetaOperatorRollbackResponse:
        records = self._read_created_resources()
        effective_dry_run = payload.force_dry_run or self.meta_client.dry_run or not self.settings.meta_autopublish
        if not payload.confirmed_by_user and not effective_dry_run:
            return MetaOperatorRollbackResponse(
                dry_run=effective_dry_run, action=payload.action, attempted=len(records), executed=0, blocked=True,
                message="Rollback real exige confirmação manual.", results=[]
            )
        results: list[dict[str, Any]] = []
        executed = 0
        for record in records:
            campaign_id = record.get("campaign_id")
            if not campaign_id:
                continue
            try:
                result = self.meta_client.remove_campaign(campaign_id, action=payload.action, dry_run=effective_dry_run)
                results.append({"campaign_id": campaign_id, "result": result})
                if not result.get("dry_run"):
                    executed += 1
            except MetaMarketingError as exc:
                results.append({"campaign_id": campaign_id, "error": str(exc)})
        response = MetaOperatorRollbackResponse(
            dry_run=effective_dry_run, action=payload.action, attempted=len(records), executed=executed, blocked=False,
            message="Rollback simulado." if effective_dry_run else "Rollback enviado para a Meta.", results=results
        )
        self._write_log({"event": "rollback", **response.model_dump(mode="json")})
        return response

    def _build_payload_preview(self, plans: list[CampaignPlanItem]) -> MetaOperatorPayloadPreview:
        plans_payload = [plan.model_dump(mode="json") for plan in plans]
        raw = json.dumps(plans_payload, ensure_ascii=False, sort_keys=True)
        payload_sha256 = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return MetaOperatorPayloadPreview(
            payload_sha256=payload_sha256,
            plans=plans_payload,
            message="Revise este JSON antes de publicar. Para produção real, envie confirmed_by_user=true e expected_payload_sha256 com este hash.",
        )

    def _publish_plan(self, plan: CampaignPlanItem) -> dict[str, Any]:
        if plan.existing_campaign_id:
            return self.meta_client.publish_plan_to_existing_campaign(plan)
        return self.meta_client.publish_campaign_plan(plan)

    def _simulate_plan(self, plan: CampaignPlanItem) -> dict[str, Any]:
        """Constroi o resultado simulado SEM jamais chamar o client de rede.

        CORRECAO R11: antes, o caminho "effective_dry_run=True" chamava
        _publish_plan(), que delega para MetaMarketingClient.publish_campaign_plan().
        A decisao real de chamar a rede dentro desse metodo do client depende
        SOMENTE de `self.meta_client.dry_run` (credentials.dry_run or not
        credentials.configured) -- ela NAO considera payload.mode nem
        settings.meta_autopublish. Ou seja, se META_DRY_RUN=false estivesse
        configurado no ambiente (mesmo com META_AUTOPUBLISH=false), um payload
        com mode="dry_run" ainda disparava uma chamada POST real para a Meta,
        e so o rotulo do resultado era forcado para "simulated" depois do fato.
        Esta funcao fecha essa lacuna: quando o operador decide effective_dry_run,
        nenhum codigo capaz de rede e executado, independente do estado do client.
        """
        suffix = hashlib.sha1(plan.campaign_name.encode("utf-8")).hexdigest()[:10]
        if plan.existing_campaign_id:
            return {
                "dry_run": True,
                "campaign_id": plan.existing_campaign_id,
                "adset_id": f"dry_adset_{suffix}",
                "creative_id": f"dry_creative_{suffix}",
                "ad_id": f"dry_ad_{suffix}",
                "messages": ["Dry-run ativo: conjunto/anuncio simulados dentro de campanha existente."],
            }
        return {
            "dry_run": True,
            "campaign_id": f"dry_campaign_{suffix}",
            "adset_id": f"dry_adset_{suffix}",
            "creative_id": f"dry_creative_{suffix}",
            "ad_id": f"dry_ad_{suffix}",
            "messages": [
                "Dry-run ativo: campanha simulada sem publicar no Facebook Ads.",
                "Configure META_DRY_RUN=false e credenciais oficiais para publicação real.",
            ],
        }

    def _validate_guardrails(self, payload: MetaOperatorLaunchRequest, payload_sha256: str, account_spend_today_brl: float | None, effective_dry_run: bool) -> list[MetaOperatorGuardrail]:
        checks: list[MetaOperatorGuardrail] = []
        meta_env = self._meta_environment()
        if not self.settings.meta_operator_enabled:
            checks.append(MetaOperatorGuardrail(name="operator_enabled", status="blocked", message="META_OPERATOR_ENABLED=false."))
        else:
            checks.append(MetaOperatorGuardrail(name="operator_enabled", status="ok", message="Operador habilitado."))

        if meta_env not in META_ENVIRONMENTS:
            checks.append(MetaOperatorGuardrail(name="meta_environment", status="blocked", message="META_ENV deve ser sandbox, test_account ou production."))
        elif meta_env == "production" and not effective_dry_run and not self.settings.meta_allow_production_real:
            checks.append(MetaOperatorGuardrail(name="production_unlock", status="blocked", message="Conta principal bloqueada: use sandbox/test_account primeiro ou defina META_ALLOW_PRODUCTION_REAL=true com aprovacao final."))
        else:
            checks.append(MetaOperatorGuardrail(name="meta_environment", status="ok", message=f"Ambiente Meta validado: {meta_env}."))

        if payload.optimization_event != "PURCHASE":
            checks.append(MetaOperatorGuardrail(name="purchase_event", status="blocked", message="V3 só publica com evento Purchase."))
        else:
            checks.append(MetaOperatorGuardrail(name="purchase_event", status="ok", message="Evento Purchase obrigatório confirmado."))

        if payload.mode != "dry_run" and not self.settings.meta_autopublish:
            checks.append(MetaOperatorGuardrail(name="autopublish", status="blocked", message="Publicação real exige META_AUTOPUBLISH=true."))
        else:
            checks.append(MetaOperatorGuardrail(name="autopublish", status="ok", message="Modo compatível com política de publicação."))

        if payload.mode == "publish_active" and not self.settings.meta_allow_active_launch:
            checks.append(MetaOperatorGuardrail(name="active_launch", status="blocked", message="Publicação ACTIVE exige META_ALLOW_ACTIVE_LAUNCH=true."))
        else:
            checks.append(MetaOperatorGuardrail(name="active_launch", status="ok", message="Status de lançamento permitido."))

        if payload.geo_preset == "CUSTOM" and not payload.custom_countries:
            checks.append(MetaOperatorGuardrail(name="geo_custom", status="blocked", message="CUSTOM exige pelo menos um país."))
        else:
            checks.append(MetaOperatorGuardrail(name="geo", status="ok", message="Cluster GEO válido."))

        if payload.geo_preset != "BRASIL" and "BR" not in payload.excluded_countries:
            checks.append(MetaOperatorGuardrail(name="exclude_brazil", status="warning", message="Brasil não está excluído; revise se quer tráfego brasileiro."))
        else:
            checks.append(MetaOperatorGuardrail(name="exclude_brazil", status="ok", message="Exclusão/seleção do Brasil coerente."))

        if len(payload.creatives) < 4:
            checks.append(MetaOperatorGuardrail(name="creative_volume", status="warning", message="V3 recomenda 4 a 6 criativos; menos que isso valida menos rápido."))
        else:
            checks.append(MetaOperatorGuardrail(name="creative_volume", status="ok", message="Volume de criativos adequado para V3."))

        if payload.existing_campaign_id and len(payload.creatives) != 1:
            checks.append(MetaOperatorGuardrail(name="existing_campaign_scope", status="blocked", message="Reuso de campanha existente exige exatamente 1 criativo para evitar duplicidade estrutural."))
        elif payload.existing_campaign_id:
            checks.append(MetaOperatorGuardrail(name="existing_campaign_scope", status="ok", message="Campanha existente sera reutilizada sem criar nova campanha."))

        if not effective_dry_run and payload.daily_budget_brl < 6:
            checks.append(MetaOperatorGuardrail(name="meta_min_budget", status="blocked", message="Meta recusou R$5/dia; use pelo menos R$6/dia para teste real pausado."))
        else:
            checks.append(MetaOperatorGuardrail(name="meta_min_budget", status="ok", message="Orcamento compativel com o minimo operacional conhecido."))

        if not effective_dry_run and account_spend_today_brl is None:
            checks.append(MetaOperatorGuardrail(name="spend_guard", status="blocked", message="Não consegui consultar o gasto diário da conta; publicação real bloqueada."))
        elif not effective_dry_run and account_spend_today_brl >= self.settings.meta_production_daily_spend_limit_brl:
            checks.append(MetaOperatorGuardrail(name="spend_guard", status="blocked", message=f"Gasto diário R${account_spend_today_brl:.2f} atingiu o limite R${self.settings.meta_production_daily_spend_limit_brl:.2f}."))
        else:
            checks.append(MetaOperatorGuardrail(name="spend_guard", status="ok", message="Limite diário de gasto validado ou dry-run ativo."))

        if not effective_dry_run and self.settings.meta_require_manual_confirmation and not payload.confirmed_by_user:
            checks.append(MetaOperatorGuardrail(name="manual_confirmation", status="blocked", message="Publicação real exige confirmação manual explícita."))
        elif not effective_dry_run and payload.expected_payload_sha256 and payload.expected_payload_sha256 != payload_sha256:
            checks.append(MetaOperatorGuardrail(name="payload_integrity", status="blocked", message="Hash do payload aprovado não bate com o payload atual."))
        else:
            checks.append(MetaOperatorGuardrail(name="manual_confirmation", status="ok", message="Confirmação/payload compatível com o modo atual."))

        return checks

    def _meta_environment(self) -> str:
        return str(getattr(self.settings, "meta_env", "sandbox") or "sandbox").strip().lower()

    def _production_real_allowed(self) -> bool:
        return self._meta_environment() != "production" or bool(getattr(self.settings, "meta_allow_production_real", False))

    def _build_plan(self, payload: MetaOperatorLaunchRequest, creative, index: int) -> CampaignPlanItem:
        countries = payload.custom_countries if payload.geo_preset == "CUSTOM" else GEO_PRESETS[payload.geo_preset]["countries"]
        excluded = [country for country in payload.excluded_countries if country not in countries]
        targeting: dict[str, Any] = {
            "geo_locations": {"countries": countries},
            "age_min": 25,
            "publisher_platforms": ["facebook", "instagram"],
            "device_platforms": ["mobile"],
            "wireless_carrier": ["Wifi"],
            "facebook_positions": ["feed", "video_feeds", "story", "facebook_reels"],
            "instagram_positions": ["stream", "story", "reels"],
        }
        if excluded:
            targeting["excluded_geo_locations"] = {"countries": excluded}

        status = "ACTIVE" if payload.mode == "publish_active" and self.settings.meta_allow_active_launch else "PAUSED"
        safe_product = " ".join(payload.product_name.strip().split())[:70]
        ad_code = f"AD{index:02d}"
        affiliate = self.affiliate_provider.replace_link(AffiliateReplaceRequest(
            ad_id=ad_code,
            creative_original=f"{creative.copy_text}\n{payload.landing_page_url}",
            destination_url=payload.landing_page_url,
            network="meta_operator",
            user_affiliate_id=payload.affiliate_id,
        ))
        return CampaignPlanItem(
            external_id=ad_code,
            product_name=payload.product_name,
            campaign_model="V3_AUTOMACAO_PRINCIPAL",
            priority=index,
            action="create_one_campaign_per_creative",
            existing_campaign_id=payload.existing_campaign_id,
            campaign_name=f"{safe_product} V3 {ad_code}",
            adset_name=f"{safe_product} V3 {ad_code} | {payload.geo_preset} | {payload.language}",
            ad_name=ad_code,
            objective="OUTCOME_SALES",
            daily_budget_brl=payload.daily_budget_brl,
            optimization_goal="OFFSITE_CONVERSIONS",
            billing_event="IMPRESSIONS",
            campaign_status=status,
            adset_status=status,
            ad_status=status,
            promoted_object=f"pixel:{payload.pixel_id}:event:PURCHASE",
            audience_notes=[
                f"GEO preset: {payload.geo_preset}",
                f"Idioma: {payload.language}",
                "Mobile only + Wi-Fi only + Facebook/Instagram manual.",
                "Threads, Messenger e Audience Network removidos.",
            ],
            targeting=targeting,
            creative_variations=[f"{creative.media_type.upper()} original: {creative.media_url or 'upload/local media pending'}"],
            copy_variations=[creative.copy_text],
            affiliate=affiliate,
            manual_review_required=payload.mode == "dry_run",
            automation_notes=[
                "V3: 1 campanha por criativo, orçamento individual.",
                "Não pausar antes de 3 dias salvo erro técnico/pixel/link.",
                "Escalar somente campeões com Purchase/ROAS/CPA saudáveis.",
            ],
        )

    @staticmethod
    def _result_from_meta(plan: CampaignPlanItem, creative_name: str, meta_result: dict[str, Any], forced_status: str | None = None) -> MetaOperatorCampaignResult:
        return MetaOperatorCampaignResult(
            creative_name=creative_name,
            campaign_name=plan.campaign_name,
            adset_name=plan.adset_name,
            ad_name=plan.ad_name,
            status=forced_status or ("published" if not meta_result.get("dry_run") else "simulated"),
            dry_run=bool(meta_result.get("dry_run")),
            meta_campaign_id=meta_result.get("campaign_id"),
            meta_adset_id=meta_result.get("adset_id"),
            meta_creative_id=meta_result.get("creative_id"),
            meta_ad_id=meta_result.get("ad_id"),
            messages=meta_result.get("messages", []),
        )

    @staticmethod
    def _blocked_result(plan: CampaignPlanItem, creative_name: str, message: str, status: str = "blocked") -> MetaOperatorCampaignResult:
        return MetaOperatorCampaignResult(
            creative_name=creative_name,
            campaign_name=plan.campaign_name,
            adset_name=plan.adset_name,
            ad_name=plan.ad_name,
            status=status,
            dry_run=True,
            messages=[message],
        )

    def _register_created_resources(self, plan: CampaignPlanItem, meta_result: dict[str, Any]) -> None:
        record = {
            "created_at": datetime.now(UTC).isoformat(),
            "product_name": plan.product_name,
            "campaign_name": plan.campaign_name,
            "campaign_id": meta_result.get("campaign_id"),
            "adset_id": meta_result.get("adset_id"),
            "creative_id": meta_result.get("creative_id"),
            "ad_id": meta_result.get("ad_id"),
        }
        path = Path(self.settings.meta_created_resources_log)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_created_resources(self) -> list[dict[str, Any]]:
        path = Path(self.settings.meta_created_resources_log)
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def _write_log(self, record: dict[str, Any]) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK:
            with OPERATOR_LOG.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
