"""Missão 81 — Integração Controlada.

Serviço de diagnóstico que resume o estado da integração das missões
51-59 e 71-80: rotas carregadas, versão do esquema de config e status M60.
"""

from __future__ import annotations

from typing import Any

from app.api import safe_router
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, config_fingerprint
from app.core.config import get_settings


def integration_status() -> dict[str, Any]:
    """Snapshot read-only do estado pós-integração M81."""
    settings = get_settings()
    fingerprint = config_fingerprint(settings)

    m60_branch_present = False
    m60_tests_present = False

    return {
        "mission": 81,
        "verdict": "ready" if not safe_router.FAILED_ROUTES else "not_ready",
        "config_schema_version": CONFIG_SCHEMA_VERSION,
        "config_fingerprint": fingerprint,
        "routes": {
            "loaded_count": len(safe_router.LOADED_ROUTES),
            "failed_count": len(safe_router.FAILED_ROUTES),
            "collision_count": len(safe_router.ROUTE_COLLISIONS),
            "failed": safe_router.FAILED_ROUTES,
            "collisions": safe_router.ROUTE_COLLISIONS,
        },
        "m60": {
            "branch_on_remote": m60_branch_present,
            "tests_present": m60_tests_present,
            "status": "not_ready",
            "reason": "Branch missao-60* ausente no origin; test_m60* inexistente (fail-closed).",
        },
        "integrated_missions": {
            "51_59": list(range(51, 60)),
            "60": None,
            "71_80": list(range(71, 81)),
        },
    }
