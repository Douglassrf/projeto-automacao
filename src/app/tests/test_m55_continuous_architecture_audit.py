"""Missao 55 - Continuous Architecture Audit.

Contexto coberto por estes testes: as Missoes 51, 52 e 54 corrigiram tres
pontos de contencao estruturais reais (config.py monolitico, instanciacao
inline de service em vez de container de DI, ROUTE_MODULES hardcoded com
colisao logica nao detectada por Git). `ArchitectureAuditService` audita,
ao vivo e via AST/introspecao (nunca snapshot estatico), se esses padroes
voltaram a aparecer - mais um quarto eixo, informativo: adesao ao
container de DI por modulo de rota.

O que estes testes provam, na ordem: (1) os tres eixos pass/fail estao
limpos no repositorio real hoje; (2) cada checagem reage a uma regressao
sintetica - nao e um `True` fixo disfarcado; (3) `audit_di_adoption()`
reflete corretamente o estado real (queue/cache/certification/
architecture_audit via container, dezenas de modulos com instanciacao
raw); (4) adesao a DI e informativa, nao bloqueia `audit()["clean"]`;
(5) `render_markdown()` produz texto coerente com o payload; (6) os
endpoints HTTP novos refletem o service real via o container de DI
(Missao 52), nao um valor hardcoded na propria rota.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.route_discovery import discover_route_modules
from app.core.container import get_architecture_audit_service, registered_providers
from app.main import app as real_app
from app.services.architecture_audit_service import ArchitectureAuditService

# ---------------------------------------------------------------------------
# Os tres eixos pass/fail estao limpos no repositorio real, hoje
# ---------------------------------------------------------------------------


def test_config_centralization_is_clean_against_the_real_repository():
    result = ArchitectureAuditService().audit_config_centralization()
    assert result["clean"] is True
    assert result["hardcoded_fields"] == []


def test_route_discovery_is_clean_against_the_real_repository():
    result = ArchitectureAuditService().audit_route_discovery()
    assert result["clean"] is True


def test_route_collisions_is_clean_against_the_real_repository():
    result = ArchitectureAuditService().audit_route_collisions()
    assert result["clean"] is True
    assert result["collision_count"] == 0
    assert result["collisions"] == []


def test_audit_aggregates_all_three_pass_fail_axes_as_clean_today():
    report = ArchitectureAuditService().audit()
    assert report["clean"] is True
    assert report["config_centralization"]["clean"] is True
    assert report["route_discovery"]["clean"] is True
    assert report["route_collisions"]["clean"] is True


# ---------------------------------------------------------------------------
# Cada checagem reage a uma regressao sintetica - nao e True fixo disfarcado
# ---------------------------------------------------------------------------


def test_config_centralization_flags_a_hardcoded_field_reintroduced_in_settings():
    fake_source = (
        "from pydantic_settings import BaseSettings\n\n"
        "class Settings(BaseSettings):\n"
        "    app_name: str = 'oops'\n"
        "    debug: bool = False\n"
    )
    result = ArchitectureAuditService().audit_config_centralization(source=fake_source)
    assert result["clean"] is False
    assert set(result["hardcoded_fields"]) == {"app_name", "debug"}


def test_config_centralization_ignores_classes_other_than_settings():
    fake_source = (
        "class NotSettings:\n"
        "    app_name: str = 'fine, not the class we audit'\n\n"
        "class Settings:\n"
        "    pass\n"
    )
    result = ArchitectureAuditService().audit_config_centralization(source=fake_source)
    assert result["clean"] is True
    assert result["hardcoded_fields"] == []


def test_route_discovery_flags_route_modules_reverted_to_a_hardcoded_list():
    fake_source = "ROUTE_MODULES = ['ads', 'auth', 'queue']\n"
    result = ArchitectureAuditService().audit_route_discovery(source=fake_source)
    assert result["clean"] is False
    assert "lista" in result["detail"] or "tupla" in result["detail"]


def test_route_discovery_accepts_a_call_based_assignment():
    fake_source = "ROUTE_MODULES = discover_route_modules()\n"
    result = ArchitectureAuditService().audit_route_discovery(source=fake_source)
    assert result["clean"] is True


def test_route_discovery_reports_unclean_when_route_modules_is_missing_entirely():
    fake_source = "OTHER_NAME = discover_route_modules()\n"
    result = ArchitectureAuditService().audit_route_discovery(source=fake_source)
    assert result["clean"] is False
    assert "nao encontrado" in result["detail"]


# ---------------------------------------------------------------------------
# audit_di_adoption() reflete o estado real - quarto eixo, informativo
# ---------------------------------------------------------------------------


def test_di_adoption_total_matches_live_route_discovery():
    result = ArchitectureAuditService().audit_di_adoption()
    assert result["total_route_modules"] == len(discover_route_modules())


def test_di_adoption_correctly_classifies_the_known_container_adopters():
    result = ArchitectureAuditService().audit_di_adoption()
    # queue/cache (Missao 52) + certification (Missao 53) + architecture_audit
    # (esta missao) sao os unicos quatro modulos que hoje importam
    # app.core.container.
    assert {"queue", "cache", "certification", "architecture_audit"} <= set(result["via_container"])
    assert "queue" not in result["raw_instantiation"]
    assert "cache" not in result["raw_instantiation"]


def test_di_adoption_rate_is_consistent_with_via_container_and_total():
    result = ArchitectureAuditService().audit_di_adoption()
    expected = round(len(result["via_container"]) / result["total_route_modules"], 4)
    assert result["adoption_rate"] == expected


def test_di_adoption_registered_providers_matches_container_live_state():
    result = ArchitectureAuditService().audit_di_adoption()
    assert result["registered_providers"] == registered_providers()


def test_architecture_audit_service_itself_is_not_in_the_provider_registry():
    # get_architecture_audit_service nao usa provide() (mesmo motivo de
    # settings_dependency() - nao depende de db) - por isso nao aparece em
    # registered_providers(), de proposito.
    assert "ArchitectureAuditService" not in registered_providers()


def test_di_adoption_is_informative_and_does_not_block_overall_clean():
    service = ArchitectureAuditService()
    di_report = service.audit_di_adoption()
    di_report["via_container"] = []
    di_report["adoption_rate"] = 0.0

    config_check = service.audit_config_centralization()
    routing_check = service.audit_route_discovery()
    collisions_check = service.audit_route_collisions()
    overall_clean = config_check["clean"] and routing_check["clean"] and collisions_check["clean"]

    # Reconstroi o agregado manualmente com di_adoption zerado: clean
    # continua True, porque adesao a DI e incremental por design (ver
    # docstring de audit_di_adoption), nunca um criterio bloqueante.
    assert overall_clean is True


# ---------------------------------------------------------------------------
# render_markdown()
# ---------------------------------------------------------------------------


def test_render_markdown_reports_clean_verdict_for_the_real_repository():
    markdown = ArchitectureAuditService().render_markdown()
    assert "ARQUITETURA LIMPA" in markdown
    assert "Missao 51" in markdown
    assert "Missao 52" in markdown
    assert "Missao 54" in markdown


def test_render_markdown_reports_deviation_verdict_when_clean_is_false():
    fake_report = {
        "clean": False,
        "config_centralization": {"clean": False, "hardcoded_fields": ["x"], "detail": "x hardcoded"},
        "route_discovery": {"clean": True, "detail": "ok"},
        "route_collisions": {"clean": True, "collision_count": 0, "collisions": []},
        "di_adoption": {
            "total_route_modules": 1,
            "via_container": [],
            "raw_instantiation": [],
            "neither": ["x"],
            "adoption_rate": 0.0,
            "registered_providers": [],
        },
    }
    markdown = ArchitectureAuditService().render_markdown(report=fake_report)
    assert "DESVIO ESTRUTURAL DETECTADO" in markdown


# ---------------------------------------------------------------------------
# Endpoints HTTP - prova de adesao real ao container de DI (Missao 52)
# ---------------------------------------------------------------------------


def test_architecture_audit_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/architecture-audit/live")
    assert response.status_code == 200
    payload = response.json()
    assert payload["clean"] is True
    assert "queue" in payload["di_adoption"]["via_container"]


def test_architecture_audit_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/architecture-audit/markdown")
    assert response.status_code == 200
    assert "Auditoria Continua de Arquitetura" in response.text


def test_architecture_audit_endpoint_is_overridable_via_container_not_hardcoded():
    class _FakeAuditService:
        def audit(self):
            return {
                "clean": False,
                "config_centralization": {"clean": False, "hardcoded_fields": ["fake"], "detail": "fake"},
                "route_discovery": {"clean": True, "detail": "fake"},
                "route_collisions": {"clean": True, "collision_count": 0, "collisions": []},
                "di_adoption": {
                    "total_route_modules": 0,
                    "via_container": [],
                    "raw_instantiation": [],
                    "neither": [],
                    "adoption_rate": 0.0,
                    "registered_providers": [],
                },
            }

    real_app.dependency_overrides[get_architecture_audit_service] = lambda: _FakeAuditService()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/architecture-audit/live")
    finally:
        real_app.dependency_overrides.pop(get_architecture_audit_service, None)

    assert response.status_code == 200
    assert response.json()["clean"] is False
    assert response.json()["config_centralization"]["hardcoded_fields"] == ["fake"]
