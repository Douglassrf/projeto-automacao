from __future__ import annotations

from typing import Any

from app.core.multi_tenant_readiness import multi_tenant_readiness
from app.services.campaign_brain import CampaignBrainAgent


PUBLIC_API_CATALOG = [
    {"path": "/api/v1/global-intelligence/enterprise-snapshot", "scope": "dashboard.read", "rate_limit": "60/min"},
    {"path": "/api/v1/global-intelligence/opportunity-brief", "scope": "insight.read", "rate_limit": "30/min"},
    {"path": "/api/v1/global-intelligence/winning-ad-score", "scope": "score.read", "rate_limit": "60/min"},
    {"path": "/api/v1/global-intelligence/market-radar", "scope": "radar.read", "rate_limit": "30/min"},
    {"path": "/api/v1/global-intelligence/commercial-api-snapshot", "scope": "plan.read", "rate_limit": "20/min"},
]


def public_api_readiness(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    tenant = multi_tenant_readiness(payload)
    requested_scope = str(payload.get("scope") or "dashboard.read")
    known_scopes = {item["scope"] for item in PUBLIC_API_CATALOG}
    blocked = list(tenant["blocked_reasons"])
    if requested_scope not in known_scopes:
        blocked.append("unknown_public_api_scope")
    if bool(payload.get("publish_external_api")):
        blocked.append("external_api_publish_forbidden_in_readiness")

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Public API Readiness",
            "niche": tenant["plan"],
            "campaign_stage": "37P",
            "outcome": "public_api_ready" if not blocked else "blocked",
            "lesson": "Public API readiness deve catalogar endpoints e escopos sem publicar API externa.",
            "metrics": {
                "requested_scope": requested_scope,
                "blocked_reasons": blocked,
                "catalog_size": len(PUBLIC_API_CATALOG),
            },
        }
    )

    return {
        "mission": "37P",
        "status": "public_api_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "external_api_published": False,
        "requested_scope": requested_scope,
        "catalog": PUBLIC_API_CATALOG,
        "tenant": tenant["tenant"],
        "blocked_reasons": sorted(set(blocked)),
        "security_requirements": [
            "api key por tenant",
            "rate limit por tenant e rota",
            "audit log por request",
            "sem endpoints de execucao real publica",
        ],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
