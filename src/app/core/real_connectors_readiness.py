from __future__ import annotations

from typing import Any

from app.core.public_api_readiness import public_api_readiness
from app.services.campaign_brain import CampaignBrainAgent


CONNECTOR_REQUIREMENTS = {
    "meta": ["sandbox_or_test_account", "access_token", "ad_account_id", "manual_approval"],
    "google": ["developer_token", "customer_id", "oauth_client", "manual_approval"],
    "tiktok": ["sandbox_app", "advertiser_id", "access_token", "manual_approval"],
    "linkedin": ["developer_app", "ad_account_id", "access_token", "manual_approval"],
    "pinterest": ["app_id", "ad_account_id", "access_token", "manual_approval"],
}


def real_connectors_readiness(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    public_api = public_api_readiness(payload)
    requested = payload.get("platforms") or list(CONNECTOR_REQUIREMENTS)
    if not isinstance(requested, list):
        requested = []

    connectors = []
    blocked = list(public_api["blocked_reasons"])
    for platform in requested:
        name = str(platform).lower()
        requirements = CONNECTOR_REQUIREMENTS.get(name)
        if not requirements:
            blocked.append(f"unsupported_connector:{name}")
            continue
        connectors.append(
            {
                "platform": name,
                "status": "readiness_only",
                "requirements": requirements,
                "network_enabled": False,
                "credentials_loaded": False,
                "real_write_enabled": False,
                "sandbox_required": True,
            }
        )
    if bool(payload.get("enable_network")):
        blocked.append("network_enable_forbidden_in_readiness")
    if bool(payload.get("load_credentials")):
        blocked.append("credential_loading_forbidden_in_readiness")

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Real Connectors Readiness",
            "niche": public_api["tenant"]["name"],
            "campaign_stage": "37R",
            "outcome": "connectors_readiness_ready" if not blocked else "blocked",
            "lesson": "Conectores reais devem passar por readiness sem rede, credenciais ou escrita real.",
            "metrics": {
                "connectors": len(connectors),
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37R",
        "status": "connectors_readiness_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "credentials_loaded": False,
        "connectors": connectors,
        "blocked_reasons": sorted(set(blocked)),
        "required_before_real_connectors": [
            "sandbox/test account por plataforma",
            "segredos em vault",
            "human approval por conector",
            "rate limit por plataforma",
            "auditoria por request externo",
        ],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
