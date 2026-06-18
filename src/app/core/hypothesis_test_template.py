from __future__ import annotations

from typing import Any

from app.core.sandbox_execution_contract import APPROVAL_PHRASE, sandbox_execution_contract
from app.core.security_brain_bridge import security_brain_review


def hypothesis_test_01_template(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    product_name = str(payload.get("product_name") or "Teste Hipotese 01")
    niche = str(payload.get("niche") or payload.get("nicho") or "produto digital")
    destination = str(payload.get("destination") or "whatsapp")
    daily_budget_brl = float(payload.get("daily_budget_brl") or 5)
    contract = sandbox_execution_contract(
        {
            "meta_env": payload.get("meta_env") or "sandbox",
            "daily_budget_brl": daily_budget_brl,
            "campaign_status": "PAUSED",
            "confirmed_by_user": bool(payload.get("confirmed_by_user")),
            "approval_phrase": payload.get("approval_phrase") or "",
            "allow_active_launch": False,
        }
    )
    brain = security_brain_review({"target": "meta"})
    return {
        "template_id": "TESTE_HIPOTESE_01",
        "status": "ready_as_safe_plan",
        "product_name": product_name,
        "niche": niche,
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "campaign": {
            "name": f"{product_name} | Teste Hipotese 01",
            "objective": "LEAD",
            "optimization_event": "LEAD",
            "status": "PAUSED",
            "daily_budget_brl": daily_budget_brl,
            "budget_policy": "maximo seguro inicial R$5/dia em sandbox/test_account",
            "audience": {
                "country": "BR",
                "age": "18-65+",
                "interests": [],
                "strategy": "broad_audience",
            },
            "destination": destination,
        },
        "creative_brief": {
            "format": "video_ugc_15s",
            "hook": "Testei um anuncio simples e descobri onde estava perdendo dinheiro.",
            "body": "Mostre o problema, a descoberta e convide para receber o modelo.",
            "cta": "Comenta EU QUERO ou chama no WhatsApp para receber o modelo.",
            "rules": [
                "sem promessa absoluta",
                "sem antes/depois enganoso",
                "sem urgencia falsa",
                "sem compra direta no primeiro teste",
            ],
        },
        "tracking": {
            "required_events": ["PageView", "ViewContent", "Lead"],
            "utm": {
                "utm_source": "meta",
                "utm_medium": "paid_social",
                "utm_campaign": "teste_hipotese_01",
                "utm_content": "ugc_15s_hook_01",
            },
            "lead_asset_required": True,
        },
        "cut_metrics": {
            "pause_if_cpa_lead_above_brl": 15,
            "good_signal_cpa_lead_brl": 4,
            "minimum_ctr_percent": 1.5,
            "watch_frequency_above": 2.5,
            "review_after_days": 3,
        },
        "sandbox_contract": contract,
        "brain_brian_review": {
            "decision": brain["brain_review"]["decision"],
            "next_action": brain["brain_review"]["next_action"],
            "learning_recorded": brain["brian_learning"]["stored"]["status"] == "stored",
        },
        "required_human_phrase_for_sandbox": APPROVAL_PHRASE,
    }
