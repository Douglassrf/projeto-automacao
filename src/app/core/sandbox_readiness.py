from __future__ import annotations

from typing import Any

from app.core.real_mode_gate import real_mode_readiness_gate
from app.core.security_brain_bridge import security_brain_review
from app.core.security_status import security_hardening_status


def sandbox_readiness_report(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    gate_payload = {
        "target": payload.get("target") or "meta",
        "confirmed_by_user": bool(payload.get("confirmed_by_user")),
        "approval_phrase": payload.get("approval_phrase") or "",
    }
    security = security_hardening_status()
    gate = real_mode_readiness_gate(gate_payload)
    brain = security_brain_review(gate_payload)
    sandbox_ready = security["status"] == "active_safe_mode" and security["controls"] and all(security["controls"].values())

    blockers = list(gate["blocked_reasons"])
    production_blockers = sorted(set(blockers + ["requires_separate_sandbox_or_test_account", "requires_final_human_confirmation"]))

    return {
        "status": "ready_for_sandbox_review" if sandbox_ready else "blocked",
        "sandbox_ready": sandbox_ready,
        "production_ready": False,
        "security_controls_active": all(security["controls"].values()),
        "real_mode_gate_status": gate["status"],
        "sandbox_recommendation": (
            "Usar somente sandbox Meta ou conta de anuncio separada, campanha pausada e orcamento minimo aprovado."
            if sandbox_ready
            else "Corrigir controles de seguranca antes de qualquer teste real."
        ),
        "production_blockers": production_blockers,
        "brain_decision": brain["brain_review"]["decision"],
        "brain_next_action": brain["brain_review"]["next_action"],
        "required_next_steps": [
            "validar conta sandbox/test_account separada",
            "confirmar payload real assistido",
            "manter campanha pausada",
            "confirmar limite de gasto antes de qualquer teste",
            "registrar aprovacao humana final",
        ],
    }
