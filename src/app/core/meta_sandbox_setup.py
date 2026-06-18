from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.sandbox_execution_contract import sandbox_execution_contract
from app.core.secrets_policy import SecretsPolicy


def meta_sandbox_setup_check(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    settings = get_settings()
    meta_env = str(payload.get("meta_env") or settings.meta_env or "sandbox").lower()
    budget = float(payload.get("daily_budget_brl") or 5)
    campaign_status = str(payload.get("campaign_status") or "PAUSED").upper()
    policy = SecretsPolicy()
    credentials = {
        "META_ACCESS_TOKEN": settings.meta_access_token,
        "META_AD_ACCOUNT_ID": settings.meta_ad_account_id,
        "META_PAGE_ID": settings.meta_page_id,
        "META_PIXEL_ID": settings.meta_pixel_id,
    }
    credential_checks = policy.audit_mapping(credentials, production=False)
    contract = sandbox_execution_contract(
        {
            "meta_env": meta_env,
            "daily_budget_brl": budget,
            "campaign_status": campaign_status,
            "confirmed_by_user": bool(payload.get("confirmed_by_user")),
            "approval_phrase": payload.get("approval_phrase") or "",
            "allow_active_launch": False,
        }
    )
    blocked: list[str] = []
    if meta_env not in {"sandbox", "test_account"}:
        blocked.append("meta_env_not_sandbox_or_test_account")
    if settings.meta_allow_active_launch:
        blocked.append("meta_allow_active_launch_must_remain_false")
    if settings.meta_autopublish:
        blocked.append("meta_autopublish_must_remain_false_for_setup")
    if budget > 5:
        blocked.append("sandbox_budget_above_5_brl")
    if campaign_status != "PAUSED":
        blocked.append("campaign_not_paused")

    return {
        "status": "ready_for_manual_sandbox_configuration" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "meta_env": meta_env,
        "credential_summary": {
            "total": credential_checks["total"],
            "warnings": credential_checks["warnings"],
            "blocked": credential_checks["blocked"],
            "checks": credential_checks["checks"],
        },
        "contract_status": contract["status"],
        "blocked_reasons": blocked,
        "manual_setup_steps": [
            "confirmar Business/Profile empresarial na Meta",
            "usar sandbox ou conta de anuncio separada",
            "confirmar pixel/eventos PageView, ViewContent e Lead",
            "gerar campanha pausada com objetivo Lead",
            "manter orcamento maximo de R$5/dia no primeiro preparo",
            "nao ativar gasto sem nova aprovacao humana",
        ],
        "safe_payload_defaults": {
            "campaign_status": "PAUSED",
            "objective": "LEAD",
            "optimization_event": "LEAD",
            "daily_budget_brl": 5,
            "allow_active_launch": False,
        },
    }
