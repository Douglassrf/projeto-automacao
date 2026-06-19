from __future__ import annotations

import json
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.meta_marketing import MetaMarketingClient, MetaMarketingError
from app.repositories.decision_log_repository import DecisionLogRepository
from app.schemas.automation_control import (
    ApplySuggestionRequest,
    ApplySuggestionResponse,
    AutomationControlStatusResponse,
    KillSwitchResponse,
)
from app.schemas.decision_logs import DecisionLogCreate
from app.services.observability import immutable_audit_event

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_DIR = PROJECT_ROOT / "data" / "runtime"
KILL_SWITCH_FILE = RUNTIME_DIR / "kill_switch.json"

LEVEL_DESCRIPTIONS = {
    0: "Nível 0: IA sugere, você analisa e executa manualmente.",
    1: "Nível 1: IA gera a ação e você confirma no botão Aplicar Sugestão.",
    2: "Nível 2: IA pode executar automaticamente na Meta API com guardrails ativos.",
}


class AutomationControlService:
    def __init__(self, db: Session, meta_client: MetaMarketingClient | None = None) -> None:
        self.db = db
        self.settings = get_settings()
        self.meta_client = meta_client or MetaMarketingClient()

    def status(self) -> AutomationControlStatusResponse:
        level = self._automation_level()
        return AutomationControlStatusResponse(
            automation_level=level,
            dry_run=self.meta_client.dry_run,
            meta_credentials_configured=self.meta_client.credentials.configured,
            kill_switch_enabled=self.is_kill_switch_enabled(),
            daily_spend_limit_brl=self.settings.automation_daily_spend_limit_brl,
            level_description=LEVEL_DESCRIPTIONS[level],
            allowed_actions=["notify_only", "pause_campaign", "pause_adset", "scale_budget"],
            required_env_for_level_1=[
                "AUTOMATION_LEVEL=1",
                "META_ACCESS_TOKEN",
                "META_AD_ACCOUNT_ID",
                "META_DRY_RUN=false para ação real; true para simulação",
            ],
            required_env_for_level_2=[
                "AUTOMATION_LEVEL=2",
                "AUTOMATION_LEVEL_2_ENABLED=true",
                "KILL_SWITCH_ENABLED=false apenas quando operação estiver segura",
                "AUTOMATION_DAILY_SPEND_LIMIT_BRL definido",
            ],
        )

    def apply_suggestion(self, payload: ApplySuggestionRequest, user_id: int | None = None) -> ApplySuggestionResponse:
        level = self._automation_level()
        now = datetime.now(UTC)
        requested_dry_run = payload.force_dry_run or self.meta_client.dry_run or level == 0
        blocked_reason = self._guardrail_block_reason(payload, level)

        # C04 (achado colateral): mesma família de guardrails de ambiente
        # (meta_env / META_ALLOW_PRODUCTION_REAL) já exigida em
        # facebook_automation.py e campaign_intelligence.py. Sem este check,
        # uma ação real (pause_campaign/pause_adset/scale_budget) com
        # AUTOMATION_LEVEL>=1, META_DRY_RUN=false e kill switch desligado
        # passava direto para a Meta sem nunca confirmar se o ambiente é
        # sandbox/produção liberada. Só roda quando a chamada seria real
        # (nunca bloqueia um pedido de dry_run).
        real_mode_blocked_reasons: list[str] = []
        if (
            blocked_reason is None
            and not requested_dry_run
            and payload.action in {"pause_campaign", "pause_adset", "scale_budget"}
        ):
            real_mode_blocked_reasons = self._real_mode_guardrails()
            if real_mode_blocked_reasons:
                blocked_reason = (
                    "Execução real bloqueada por guardrails de ambiente: "
                    + ", ".join(real_mode_blocked_reasons)
                    + "."
                )

        action_executed = False
        meta_response: dict[str, Any]

        if blocked_reason:
            meta_response = {"status": "blocked", "reason": blocked_reason}
            if real_mode_blocked_reasons:
                immutable_audit_event(
                    actor="AutomationControlService",
                    action="automation_control.apply_suggestion.blocked",
                    resource_type="meta_action",
                    resource_id=str(payload.campaign_id),
                    status="blocked",
                    details={"action": payload.action, "reasons": real_mode_blocked_reasons},
                )
        elif payload.action == "notify_only":
            meta_response = {"status": "notified", "message": "Ação registrada no feed; nenhuma alteração enviada à Meta."}
        else:
            try:
                meta_response = self.meta_client.apply_campaign_action(
                    action=payload.action,
                    campaign_id=payload.campaign_id,
                    adset_id=payload.adset_id,
                    target=payload.target,
                    new_daily_budget_brl=payload.new_daily_budget_brl,
                    dry_run=requested_dry_run,
                )
                action_executed = not meta_response.get("dry_run", False)
                if action_executed:
                    immutable_audit_event(
                        actor="AutomationControlService",
                        action="automation_control.apply_suggestion.published",
                        resource_type="meta_action",
                        resource_id=str(payload.campaign_id),
                        status="ok",
                        details={"action": payload.action},
                    )
            except MetaMarketingError as exc:
                blocked_reason = str(exc)
                meta_response = {"status": "meta_error", "message": str(exc)}

        reasoning = self._reasoning(payload, level, blocked_reason, action_executed, meta_response)
        decision = DecisionLogRepository(self.db).create(DecisionLogCreate(
            user_id=user_id,
            campaign_id=payload.campaign_id,
            product_name="Meta Automation Control",
            reason_code=payload.reason_code,
            metric_name=payload.metric_name,
            metric_value=payload.metric_value,
            threshold_value=payload.threshold_value,
            severity="danger" if blocked_reason else ("success" if action_executed else "warning"),
            tag_label="Ação executada" if action_executed else ("Atenção urgente" if blocked_reason else "Aguardando confirmação"),
            action_taken=payload.action,
            reasoning=reasoning,
        ))
        return ApplySuggestionResponse(
            timestamp=now,
            automation_level=level,
            action_requested=payload.action,
            action_executed=action_executed,
            dry_run=bool(meta_response.get("dry_run", requested_dry_run)),
            blocked=blocked_reason is not None,
            blocked_reason=blocked_reason,
            campaign_id=payload.campaign_id,
            adset_id=payload.adset_id,
            meta_response=meta_response,
            decision_log_id=decision.id,
            reasoning=reasoning,
        )

    def set_kill_switch(self, enabled: bool, reason: str) -> KillSwitchResponse:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"enabled": enabled, "changed_at": datetime.now(UTC).isoformat(), "reason": reason}
        KILL_SWITCH_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return KillSwitchResponse(enabled=enabled, changed_at=datetime.fromisoformat(payload["changed_at"]), reason=reason)

    def is_kill_switch_enabled(self) -> bool:
        if self.settings.kill_switch_enabled:
            return True
        if not KILL_SWITCH_FILE.exists():
            return False
        try:
            return bool(json.loads(KILL_SWITCH_FILE.read_text(encoding="utf-8")).get("enabled"))
        except json.JSONDecodeError:
            return True

    def _automation_level(self) -> int:
        level = max(0, min(2, int(self.settings.automation_level)))
        if level == 2 and not self.settings.automation_level_2_enabled:
            return 1
        return level

    def _guardrail_block_reason(self, payload: ApplySuggestionRequest, level: int) -> str | None:
        if self.is_kill_switch_enabled():
            return "Kill Switch ativo: 