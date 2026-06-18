from __future__ import annotations

from typing import Any

from app.core.sandbox_readiness import sandbox_readiness_report


APPROVAL_PHRASE = "EU APROVO TESTE SANDBOX PAUSADO SEM GASTO ATIVO"


def sandbox_execution_contract(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    blocked: list[str] = []
    meta_env = str(payload.get("meta_env") or "sandbox").lower()
    daily_budget_brl = float(payload.get("daily_budget_brl") or 0)
    campaign_status = str(payload.get("campaign_status") or "PAUSED").upper()
    approval_phrase = str(payload.get("approval_phrase") or "")
    confirmed_by_user = bool(payload.get("confirmed_by_user"))

    if meta_env not in {"sandbox", "test_account"}:
        blocked.append("meta_env_must_be_sandbox_or_test_account")
    if campaign_status != "PAUSED":
        blocked.append("campaign_must_remain_paused")
    if daily_budget_brl <= 0:
        blocked.append("daily_budget_required")
    if daily_budget_brl > 5:
        blocked.append("daily_budget_above_sandbox_limit")
    if bool(payload.get("allow_active_launch")):
        blocked.append("active_launch_forbidden")
    if not confirmed_by_user or approval_phrase != APPROVAL_PHRASE:
        blocked.append("sandbox_human_approval_required")

    readiness = sandbox_readiness_report({"target": "meta"})
    return {
        "status": "contract_valid" if not blocked else "blocked",
        "can_prepare_sandbox_execution": not blocked,
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "required_approval_phrase": APPROVAL_PHRASE,
        "blocked_reasons": blocked,
        "contract": {
            "allowed_envs": ["sandbox", "test_account"],
            "campaign_status_required": "PAUSED",
            "max_daily_budget_brl": 5,
            "active_launch_allowed": False,
            "requires_final_human_action": True,
        },
        "readiness_status": readiness["status"],
        "production_ready": False,
    }
