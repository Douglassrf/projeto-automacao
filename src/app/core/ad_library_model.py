from __future__ import annotations

from typing import Any

from app.core.data_moat import data_moat_local_snapshot
from app.core.multi_tenant_readiness import multi_tenant_readiness
from app.core.vector_db_readiness import vector_db_readiness
from app.services.campaign_brain import CampaignBrainAgent


SENSITIVE_FIELDS_FORBIDDEN = {
    "access_token",
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
}

AD_LIBRARY_SCHEMA = {
    "ads": [
        "ad_id",
        "fingerprint",
        "tenant_id",
        "workspace_id",
        "source",
        "platform",
        "country",
        "language",
        "currency",
        "niche",
        "headline",
        "body",
        "cta",
        "creative_type",
        "landing_url",
        "landing_domain",
        "offer_type",
        "ticket",
        "score",
        "angle",
        "emotion",
        "risk_flags",
        "first_seen",
        "last_seen",
        "created_at",
    ],
    "ad_metrics": [
        "ad_id",
        "tenant_id",
        "workspace_id",
        "impressions",
        "clicks",
        "leads",
        "spend",
        "ctr",
        "cpa",
        "roas",
        "observed_at",
    ],
    "ad_vectors": [
        "ad_id",
        "tenant_id",
        "workspace_id",
        "vector_namespace",
        "embedding_provider",
        "embedding_dimension",
        "metadata_hash",
        "created_at",
    ],
    "ad_tags": [
        "ad_id",
        "tenant_id",
        "workspace_id",
        "tag_type",
        "tag_value",
        "confidence",
        "created_by",
        "created_at",
    ],
    "ad_audit": [
        "event_id",
        "ad_id",
        "tenant_id",
        "workspace_id",
        "actor",
        "action",
        "correlation_id",
        "created_at",
    ],
}


def _payload_sensitive_keys(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        keys: list[str] = []
        for key, nested in value.items():
            key_text = str(key).lower()
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text in SENSITIVE_FIELDS_FORBIDDEN or any(part in key_text for part in ("token", "secret", "password")):
                keys.append(path)
            keys.extend(_payload_sensitive_keys(nested, path))
        return keys
    if isinstance(value, list):
        keys = []
        for idx, item in enumerate(value[:10]):
            keys.extend(_payload_sensitive_keys(item, f"{prefix}[{idx}]"))
        return keys
    return []


def ad_library_data_model(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    blocked: list[str] = []
    if bool(payload.get("persist_ads")):
        blocked.append("ad_library_persistence_forbidden_in_local_readiness")
    sensitive_keys = _payload_sensitive_keys(payload)
    if sensitive_keys:
        blocked.append("sensitive_fields_forbidden_in_ad_library_payload")

    tenant = multi_tenant_readiness(payload)
    vector = vector_db_readiness(payload)
    moat = data_moat_local_snapshot(payload)
    blocked.extend(tenant["blocked_reasons"])
    blocked.extend(vector["blocked_reasons"])

    tenant_id = tenant["tenant"]["tenant_id"]
    workspace_id = tenant["tenant"]["workspace_id"]
    namespace = vector["tenant_namespace"]
    platform = next(iter(moat["platform_counts"]), "unknown")
    country = next(iter(moat["country_counts"]), "unknown")
    niche = next(iter(moat["niche_counts"]), "unknown")
    records_preview = [
        {
            "ad_id": f"ad_{fingerprint}",
            "fingerprint": fingerprint,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "platform": platform,
            "country": country,
            "niche": niche,
            "vector_namespace": namespace,
            "contains_sensitive_data": False,
        }
        for fingerprint in moat["fingerprints"][:5]
    ]

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Ad Library Data Model Local",
            "niche": niche,
            "campaign_stage": "37T",
            "outcome": "ad_library_model_ready" if not blocked else "blocked",
            "lesson": "Biblioteca de anuncios deve ser um modelo seguro, multi-tenant e vetorial-ready antes de armazenar dados reais.",
            "metrics": {
                "tables": len(AD_LIBRARY_SCHEMA),
                "records_preview": len(records_preview),
                "blocked_reasons": blocked,
                "large_local_storage_used": False,
            },
        }
    )

    return {
        "mission": "37T",
        "status": "ad_library_model_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "database_write_used": False,
        "large_local_storage_used": False,
        "schema": AD_LIBRARY_SCHEMA,
        "storage_plan": {
            "local_preview_path": "data/ad_library/",
            "production_recommendation": "PostgreSQL + pgvector em servidor/VPS, nao no laptop",
            "zip_includes_data": False,
            "raw_media_storage": "object_storage_s3_or_compatible",
        },
        "tenant": tenant["tenant"],
        "records_preview": records_preview,
        "sensitive_keys_detected": sorted(set(sensitive_keys)),
        "blocked_reasons": sorted(set(blocked)),
        "migration_steps": [
            "criar tabelas com tenant_id e workspace_id obrigatorios",
            "guardar midia pesada em object storage, nao no banco principal",
            "guardar embeddings em pgvector com namespace por tenant",
            "aplicar RBAC, audit log e human approval antes de ingestao real",
            "manter data/ fora do pacote seguro e fora do Git",
        ],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
