from __future__ import annotations

from typing import Any

from app.core.commercial_api_snapshot import PLAN_LIMITS, commercial_api_snapshot
from app.services.campaign_brain import CampaignBrainAgent


PLAN_PRICES_USD = {"starter": 49, "growth": 199, "enterprise": 999}


def billing_readiness_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    plan = str(payload.get("plan") or "starter").lower()
    commercial = commercial_api_snapshot(payload)
    blocked = list(commercial["blocked_reasons"])
    if plan not in PLAN_LIMITS:
        blocked.append("billing_plan_unknown")
    if bool(payload.get("enable_real_billing")):
        blocked.append("real_billing_forbidden_in_local_readiness")

    price = PLAN_PRICES_USD.get(plan, PLAN_PRICES_USD["starter"])
    invoice_preview = {
        "plan": plan,
        "currency": "USD",
        "monthly_price": price,
        "status": "preview_only",
        "payment_methods_enabled": [],
        "will_charge": False,
    }

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Billing Readiness {plan}",
            "niche": "saas",
            "campaign_stage": "37N",
            "outcome": "billing_preview_ready" if not blocked else "blocked",
            "lesson": "Billing readiness deve prever planos e precos sem ativar cobranca real.",
            "metrics": {
                "plan": plan,
                "price_usd": price,
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37N",
        "status": "billing_preview_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "will_charge_customer": False,
        "billing_provider_connected": False,
        "plan": plan,
        "invoice_preview": invoice_preview,
        "plan_limits": PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"]),
        "blocked_reasons": sorted(set(blocked)),
        "required_before_real_billing": [
            "empresa/legal definido",
            "termos de uso e politica de privacidade",
            "gateway de pagamento aprovado",
            "webhook assinado e auditado",
            "aprovacao humana para ativar cobranca",
        ],
        "commercial_snapshot_status": commercial["status"],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
