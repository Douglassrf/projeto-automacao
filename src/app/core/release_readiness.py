from __future__ import annotations

from typing import Any

from app.core.saas_compliance import saas_compliance_local
from app.core.scale_forecast import scale_forecast_local
from app.core.security_status import security_hardening_status
from app.services.campaign_brain import CampaignBrainAgent


EXPECTED_RELEASE_TESTS = "258 passed"


def release_readiness_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    blocked: list[str] = []
    if bool(payload.get("deploy_now")):
        blocked.append("deploy_forbidden_in_release_readiness")
    if bool(payload.get("enable_billing")):
        blocked.append("billing_activation_forbidden_in_release_readiness")
    if bool(payload.get("enable_public_api")):
        blocked.append("public_api_activation_forbidden_in_release_readiness")
    if bool(payload.get("enable_real_meta")):
        blocked.append("real_meta_activation_forbidden_in_release_readiness")

    security = security_hardening_status()
    compliance = saas_compliance_local(payload)
    forecast = scale_forecast_local(payload)
    blocked.extend(compliance["blocked_reasons"])
    blocked.extend(forecast["blocked_reasons"])

    controls_active = all(security["controls"].values())
    if not controls_active:
        blocked.append("security_controls_incomplete")
    checklist = {
        "tests_expected": EXPECTED_RELEASE_TESTS,
        "security_controls_active": controls_active,
        "compliance_ready": compliance["status"] == "compliance_ready",
        "forecast_ready": forecast["status"] == "scale_forecast_ready",
        "package_must_exclude_env": True,
        "package_must_exclude_data": True,
        "manual_approval_required": True,
        "deploy_blocked": True,
        "billing_blocked": True,
        "real_meta_blocked": True,
    }
    ready_items = sum(1 for value in checklist.values() if value is True)
    readiness_score = round((ready_items / len(checklist)) * 100, 2)

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Release Readiness Local",
            "niche": payload.get("niche") or "global intelligence",
            "campaign_stage": "38A",
            "outcome": "release_readiness_ready" if not blocked else "blocked",
            "lesson": "Release readiness deve validar seguranca, compliance, forecast e pacote sem deploy, billing ou Meta real.",
            "metrics": {
                "readiness_score": readiness_score,
                "blocked_reasons": blocked,
                "tests_expected": EXPECTED_RELEASE_TESTS,
            },
        }
    )

    return {
        "mission": "38A",
        "status": "release_readiness_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "deploy_used": False,
        "billing_enabled": False,
        "public_api_enabled": False,
        "real_meta_enabled": False,
        "readiness_score": readiness_score,
        "checklist": checklist,
        "source_modules": {
            "security_status": "36D",
            "saas_compliance": compliance["mission"],
            "scale_forecast": forecast["mission"],
        },
        "blocked_reasons": sorted(set(blocked)),
        "release_gate": "human_review_only",
        "recommended_next_step": "rodar smoke test local de produto antes de qualquer deploy",
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
