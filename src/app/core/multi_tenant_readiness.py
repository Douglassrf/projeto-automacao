from __future__ import annotations

import hashlib
from typing import Any

from app.core.commercial_api_snapshot import commercial_api_snapshot
from app.core.security_hardening import SecurityRole, allowed_permissions
from app.services.campaign_brain import CampaignBrainAgent


def _stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def multi_tenant_readiness(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    tenant_name = str(payload.get("tenant") or payload.get("organization") or "").strip()
    workspace_name = str(payload.get("workspace") or "default").strip()
    actor_role = str(payload.get("role") or "VIEWER").upper()
    requested_tenant = str(payload.get("requested_tenant") or tenant_name).strip()
    blocked: list[str] = []

    if not tenant_name:
        blocked.append("tenant_required")
        tenant_name = "missing"
    if not workspace_name:
        blocked.append("workspace_required")
        workspace_name = "default"
    if requested_tenant and requested_tenant != tenant_name:
        blocked.append("cross_tenant_access_forbidden")
    try:
        permissions = allowed_permissions(SecurityRole(actor_role))
    except ValueError:
        permissions = []
        blocked.append("invalid_role")

    commercial = commercial_api_snapshot(payload)
    blocked.extend(commercial["blocked_reasons"])
    tenant_id = _stable_id(tenant_name)
    workspace_id = _stable_id(f"{tenant_name}:{workspace_name}")
    data_partition = f"tenant/{tenant_id}/workspace/{workspace_id}"

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": f"Multi Tenant {tenant_id}",
            "niche": commercial["plan"],
            "campaign_stage": "37O",
            "outcome": "tenant_ready" if not blocked else "blocked",
            "lesson": "Multi-tenant readiness deve isolar tenant, workspace, permissoes e particao de dados antes de SaaS real.",
            "metrics": {
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "blocked_reasons": blocked,
                "role": actor_role,
            },
        }
    )

    return {
        "mission": "37O",
        "status": "tenant_ready" if not blocked else "blocked",
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "tenant_storage_enabled": False,
        "tenant": {
            "name": tenant_name,
            "tenant_id": tenant_id,
            "workspace": workspace_name,
            "workspace_id": workspace_id,
            "data_partition": data_partition,
        },
        "actor": {
            "role": actor_role,
            "permissions": permissions,
        },
        "plan": commercial["plan"],
        "limits": commercial["limits"],
        "blocked_reasons": sorted(set(blocked)),
        "isolation_rules": [
            "todo dado deve carregar tenant_id e workspace_id",
            "cross-tenant e bloqueado por padrao",
            "service accounts nao usam login humano",
            "sem persistencia multi-tenant real nesta missao",
        ],
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
