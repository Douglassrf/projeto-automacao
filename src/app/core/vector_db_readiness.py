from __future__ import annotations

from typing import Any

from app.core.data_moat import data_moat_local_snapshot
from app.core.multi_tenant_readiness import multi_tenant_readiness
from app.services.campaign_brain import CampaignBrainAgent


VECTOR_PROVIDERS = {
    "local_preview": {"dimension": 16, "external": False, "production_ready": False},
    "pgvector": {"dimension": 1536, "external": False, "production_ready": True},
    "qdrant": {"dimension": 1536, "external": True, "production_ready": True},
}


def vector_db_readiness(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    provider = str(payload.get("vector_provider") or "local_preview").lower()
    provider_config = VECTOR_PROVIDERS.get(provider)
    blocked: list[str] = []
    if provider_config is None:
        blocked.append("unsupported_vector_provider")
        provider = "local_preview"
        provider_config = VECTOR_PROVIDERS[provider]
    if bool(payload.get("connect_vector_db")):
        blocked.append("vector_db_connection_forbidden_in_readiness")
    if bool(payload.get("generate_paid_embeddings")):
        blocked.append("paid_embeddings_forbidden_in_readiness")

    tenant = multi_tenant_readiness(payload)
    moat = data_moat_local_snapshot(payload)
    blocked.extend(tenant["blocked_reasons"])
    documents = [
        {
            "fingerprint": fingerprint,
            "tenant_id": tenant["tenant"]["tenant_id"],
            "workspace_id": tenant["tenant"]["workspace_id"],
            "namespace": tenant["tenant"]["data_partition"],
            "embedding_preview": [round((idx + 1) / 100, 2) for idx in range(provider_config["dimension"])][:16],
            "metadata_fields": ["platform", "country", "niche", "score", "angle", "emotion", "first_seen"],
        }
        for fingerprint in moat["fingerprints"][:5]
    ]

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Vector DB Readiness {provider}",
            "niche": next(iter(moat["niche_counts"]), "sem sinal") if moat["niche_counts"] else "sem sinal",
            "campaign_stage": "37S",
            "outcome": "vector_readiness_ready" if not blocked else "blocked",
            "lesson": "Vector DB readiness deve preparar schema, namespace e embeddings preview sem conectar banco externo.",
            "metrics": {
                "provider": provider,
                "documents_preview": len(documents),
                "blocked_reasons": blocked,
            },
        }
    )

    return {
        "mission": "37S",
        "status": "vector_readiness_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "vector_db_connected": False,
        "paid_embeddings_generated": False,
        "provider": provider,
        "provider_config": provider_config,
        "storage_plan": {
            "local_preview_path": "data/vector_memory/",
            "production_recommendation": "PostgreSQL + pgvector",
            "zip_includes_data": False,
        },
        "tenant_namespace": tenant["tenant"]["data_partition"],
        "documents_preview": documents,
        "blocked_reasons": sorted(set(blocked)),
        "migration_steps": [
            "criar schema com tenant_id e workspace_id obrigatorios",
            "armazenar embedding separado de metadata sensivel",
            "aplicar RBAC e isolamento por namespace",
            "ativar backup antes de ingestao real",
        ],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
