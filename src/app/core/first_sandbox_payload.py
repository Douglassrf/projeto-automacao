from __future__ import annotations

from typing import Any

from app.core.hypothesis_test_template import hypothesis_test_01_template
from app.core.meta_sandbox_setup import meta_sandbox_setup_check
from app.core.sandbox_execution_contract import APPROVAL_PHRASE, sandbox_execution_contract


def first_sandbox_paused_payload(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    meta_env = str(payload.get("meta_env") or "sandbox").lower()
    daily_budget_brl = float(payload.get("daily_budget_brl") or 5)
    campaign_status = str(payload.get("campaign_status") or "PAUSED").upper()
    approval_phrase = str(payload.get("approval_phrase") or "")
    confirmed_by_user = bool(payload.get("confirmed_by_user"))

    contract_payload = {
        "meta_env": meta_env,
        "daily_budget_brl": daily_budget_brl,
        "campaign_status": campaign_status,
        "confirmed_by_user": confirmed_by_user,
        "approval_phrase": approval_phrase,
        "allow_active_launch": False,
    }
    contract = sandbox_execution_contract(contract_payload)
    setup = meta_sandbox_setup_check(contract_payload)
    template = hypothesis_test_01_template(
        {
            **payload,
            "meta_env": meta_env,
            "daily_budget_brl": daily_budget_brl,
            "confirmed_by_user": confirmed_by_user,
            "approval_phrase": approval_phrase,
        }
    )

    blocked = sorted(set(contract["blocked_reasons"] + setup["blocked_reasons"]))
    if campaign_status != template["campaign"]["status"]:
        blocked.append("template_payload_status_mismatch")
    if template["campaign"]["daily_budget_brl"] > 5:
        blocked.append("template_payload_budget_above_limit")

    ready = not blocked
    return {
        "mission": "36L",
        "status": "payload_ready_for_manual_sandbox_review" if ready else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "can_send_to_meta_api": False,
        "requires_manual_final_step": True,
        "blocked_reasons": blocked,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_received": confirmed_by_user and approval_phrase == APPROVAL_PHRASE,
        "payload": {
            "meta_env": meta_env,
            "campaign_name": template["campaign"]["name"],
            "objective": template["campaign"]["objective"],
            "optimization_event": template["campaign"]["optimization_event"],
            "status": "PAUSED",
            "daily_budget_brl": daily_budget_brl,
            "destination": template["campaign"]["destination"],
            "audience": template["campaign"]["audience"],
            "creative_brief": template["creative_brief"],
            "tracking": template["tracking"],
            "cut_metrics": template["cut_metrics"],
            "safety": {
                "active_launch_allowed": False,
                "autopublish_allowed": False,
                "spend_activation_allowed": False,
                "production_allowed": False,
            },
        },
        "contract_status": contract["status"],
        "setup_status": setup["status"],
        "brain_brian_review": template["brain_brian_review"],
        "manual_next_steps": [
            "revisar payload no painel antes de qualquer chamada real",
            "usar somente sandbox Meta ou conta de anuncio separada",
            "manter campanha criada como PAUSED",
            "nao ativar gasto sem nova aprovacao humana explicita",
        ],
    }
