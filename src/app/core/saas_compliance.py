from __future__ import annotations

from typing import Any

from app.core.ad_library_model import ad_library_data_model
from app.core.multi_tenant_readiness import multi_tenant_readiness
from app.services.campaign_brain import CampaignBrainAgent


REGION_RULES = {
    "BR": {"framework": "LGPD", "requires_consent": True, "max_retention_days": 365},
    "US": {"framework": "State privacy readiness", "requires_consent": True, "max_retention_days": 365},
    "CA": {"framework": "PIPEDA", "requires_consent": True, "max_retention_days": 365},
    "GB": {"framework": "UK GDPR", "requires_consent": True, "max_retention_days": 365},
    "DE": {"framework": "GDPR", "requires_consent": True, "max_retention_days": 365},
    "FR": {"framework": "GDPR", "requires_consent": True, "max_retention_days": 365},
    "ES": {"framework": "GDPR", "requires_consent": True, "max_retention_days": 365},
    "PT": {"framework": "GDPR", "requires_consent": True, "max_retention_days": 365},
}

FORBIDDEN_DATA_TYPES = {"password", "secret", "token", "credit_card", "cpf", "ssn", "health_data"}


def saas_compliance_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    blocked: list[str] = []
    requested_regions = payload.get("regions") or [payload.get("country") or "BR"]
    regions = [str(region).upper() for region in requested_regions if str(region).strip()]
    retention_days = int(payload.get("retention_days") or 365)
    data_types = {str(item).lower() for item in payload.get("data_types", ["ad_metadata", "metrics", "creative_text"])}

    if bool(payload.get("enable_real_scraping")):
        blocked.append("real_scraping_requires_legal_review")
    if bool(payload.get("export_personal_data")):
        blocked.append("personal_data_export_requires_approval")
    if data_types & FORBIDDEN_DATA_TYPES:
        blocked.append("forbidden_sensitive_data_type")
    for region in regions:
        rule = REGION_RULES.get(region)
        if rule is None:
            blocked.append(f"unsupported_region_{region.lower()}")
            continue
        if retention_days > rule["max_retention_days"]:
            blocked.append(f"retention_exceeds_{rule['framework'].lower().replace(' ', '_')}")
    if not bool(payload.get("consent_policy_documented", True)):
        blocked.append("consent_policy_required")

    tenant = multi_tenant_readiness(payload)
    library = ad_library_data_model(payload)
    blocked.extend(tenant["blocked_reasons"])
    blocked.extend(library["blocked_reasons"])

    frameworks = [REGION_RULES[region]["framework"] for region in regions if region in REGION_RULES]
    checklist = [
        "mapear base legal por fonte de dado",
        "separar dados por tenant/workspace",
        "registrar audit log para coleta, busca, exportacao e delecao",
        "manter tokens fora de payloads e fora do pacote",
        "bloquear scraping real ate revisao juridica e aprovacao humana",
        "definir retencao e rotina de delecao por regiao",
    ]

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "SaaS Compliance Local",
            "niche": tenant["plan"],
            "campaign_stage": "37V",
            "outcome": "compliance_ready" if not blocked else "blocked",
            "lesson": "SaaS global precisa validar regiao, retencao, consentimento e dados sensiveis antes de coletar ou vender inteligencia.",
            "metrics": {
                "regions": regions,
                "frameworks": frameworks,
                "blocked_reasons": blocked,
                "retention_days": retention_days,
            },
        }
    )

    return {
        "mission": "37V",
        "status": "compliance_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "database_write_used": False,
        "legal_review_completed": False,
        "regions": regions,
        "frameworks": sorted(set(frameworks)),
        "data_types": sorted(data_types),
        "retention_days": retention_days,
        "tenant_partition": tenant["tenant"]["data_partition"],
        "ad_library_ready": library["status"] == "ad_library_model_ready",
        "blocked_reasons": sorted(set(blocked)),
        "compliance_checklist": checklist,
        "human_approval_required_for": [
            "real_scraping",
            "personal_data_export",
            "external_api_publication",
            "billing_activation",
            "data_retention_change",
        ],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
