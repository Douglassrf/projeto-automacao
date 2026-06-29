"""Missao 81 - Integracao Controlada das Equipes (CAPSTONE).

Agrega sinais de saude pos-merge: rotas carregadas/falhas/colisoes,
dominios de config descobertos, versao do esquema e contagem de testes
esperados por frente integrada. Fail-closed quando qualquer indicador
critico falha.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.api import safe_router
from app.core.config import Settings, get_settings
from app.core.config_loader import domain_summary
from app.core.config_profiles import CONFIG_SCHEMA_VERSION


@dataclass
class IntegrationControlService:
    """Verificacao unificada de saude pos-integracao M81."""

    settings: Settings

    def merge_health_report(self) -> dict[str, Any]:
        summary = domain_summary()
        field_names = sorted(Settings.model_fields.keys())
        blocking: list[str] = []

        if safe_router.FAILED_ROUTES:
            blocking.append(
                f"{len(safe_router.FAILED_ROUTES)} modulo(s) de rota falharam ao carregar"
            )
        if safe_router.ROUTE_COLLISIONS:
            blocking.append(
                f"{len(safe_router.ROUTE_COLLISIONS)} colisao(oes) logica(s) de rota detectada(s)"
            )
        if len(field_names) != sum(len(v) for v in summary.values()):
            blocking.append("config_domains/ nao cobre todos os campos de Settings")

        integrated_missions = {
            "41-50": {"routes": 10, "config_domains": 10},
            "51-59": {"services": 9, "routes": 9},
            "71-80": {"services": 10, "routes": 10, "config_domains": 10},
        }

        return {
            "status": "ok" if not blocking else "degraded",
            "verdict": "ready" if not blocking else "not_ready",
            "blocking_issues": blocking,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "config_field_count": len(field_names),
            "config_domain_count": len(summary),
            "loaded_routes": len(safe_router.LOADED_ROUTES),
            "failed_routes": safe_router.FAILED_ROUTES,
            "route_collisions": safe_router.ROUTE_COLLISIONS,
            "integrated_missions": integrated_missions,
            "mission_60_status": "not_ready",
            "mission_60_note": (
                "Branch missao-60 inexistente no remoto; teste dedicado nao executado."
            ),
        }


def get_integration_control_service() -> IntegrationControlService:
    return IntegrationControlService(settings=get_settings())
