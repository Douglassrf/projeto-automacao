"""Missao 54 - Merge Conflict Prevention.

Cobre dois mecanismos novos:

1. `app/api/route_discovery.py::discover_route_modules()` - substitui a
   lista `ROUTE_MODULES` (editada a mao em `safe_router.py`) por
   descoberta automatica via `pkgutil`, igual ao padrao ja usado pela
   Missao 51 (`config_domains/`). Garante que nenhum modulo de rota
   ja existente foi perdido na troca, e prova (com um diretorio falso)
   que uma rota nova passa a ser descoberta sem editar nenhuma lista
   compartilhada.
2. `extract_operations()` + `find_collisions()` - detectam colisao
   *logica* de metodo+path entre dois modulos de rota diferentes, um
   tipo de conflito que o Git nunca veria (arquivos/linhas diferentes)
   mas que deixaria uma rota silenciosamente inalcancavel.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import app.api.routes as routes_package
import app.api.safe_router as safe_router_module
from app.api.route_discovery import discover_route_modules, extract_operations, find_collisions
from app.api.safe_router import FAILED_ROUTES, LOADED_ROUTES, ROUTE_COLLISIONS, ROUTE_MODULES

# Snapshot congelado da lista ROUTE_MODULES que existia, hardcoded, em
# safe_router.py antes desta missao. Usado apenas como regressao: garante
# que a descoberta automatica nao "perdeu" nenhum modulo que ja estava
# registrado quando a lista foi substituida.
_HISTORICAL_ROUTE_MODULES = {
    "ads", "affiliate", "upload", "automation", "auth", "facebook",
    "meta_operator", "campaign_templates", "campaign_brain", "master_context",
    "meta_updates", "war_kit", "learning_loop", "learning_loop_safe",
    "learning_loop_bridge", "knowledge", "decision_logs", "decision_feed_safe",
    "automation_control", "video_pipeline", "site_builder", "orchestration",
    "hybrid_stack", "zero_cost_stack", "content_orchestrator",
    "content_orchestrator_safe", "video_pipeline_safe", "premium_render_safe",
    "site_builder_safe", "orchestration_safe", "serverless_render", "queue",
    "cache", "diagnostics", "resources", "system_alerts", "recovery",
    "documentation", "dependency_audit", "certification", "ugc_processing",
    "capi_enterprise", "premium_render", "observability", "security",
    "agency_operator", "campaign_intelligence", "campaign_intelligence_safe",
    "global_intelligence", "dashboard", "production_readiness",
    "mission_orchestrator",
}


# --- Secao 1: descoberta automatica substitui a lista hardcoded -----------


def test_route_modules_matches_files_actually_on_disk():
    on_disk = {
        path.stem
        for path in Path(routes_package.__path__[0]).glob("*.py")
        if not path.stem.startswith("_")
    }
    assert set(ROUTE_MODULES) == on_disk


def test_discover_route_modules_is_sorted_and_deterministic():
    first = discover_route_modules()
    second = discover_route_modules()
    assert first == second
    assert first == sorted(first)


def test_route_modules_equals_live_discovery_no_hardcoded_list():
    assert ROUTE_MODULES == discover_route_modules()


def test_no_previously_registered_module_was_lost_in_the_refactor():
    missing = _HISTORICAL_ROUTE_MODULES - set(ROUTE_MODULES)
    assert missing == set()


def test_safe_router_source_contains_no_hardcoded_module_list():
    """Garante que a substituicao e real, nao decorativa: o codigo-fonte
    de safe_router.py nao pode conter a lista antiga nem o `.append(...)`
    que era usado para contornar a edicao da lista compartilhada."""
    source = inspect.getsource(safe_router_module)
    assert "ROUTE_MODULES = [" not in source
    assert "ROUTE_MODULES.append(" not in source
    assert '"ads"' not in source
    assert '"mission_orchestrator"' not in source


def test_discover_route_modules_picks_up_a_new_file_with_zero_shared_list_edits(tmp_path, monkeypatch):
    """Prova positiva de adocao: criar um arquivo novo no diretorio (sem
    tocar em nenhuma lista, nenhum import, nenhum arquivo central) e
    confirma que ele aparece na descoberta - exatamente o problema que
    motivou esta missao."""
    (tmp_path / "alpha_demo.py").write_text("# fake route module\n")
    (tmp_path / "beta_demo.py").write_text("# fake route module\n")
    (tmp_path / "_private.py").write_text("# deve ser ignorado\n")
    (tmp_path / "__init__.py").write_text("")

    monkeypatch.setattr(routes_package, "__path__", [str(tmp_path)])

    assert discover_route_modules() == ["alpha_demo", "beta_demo"]


# --- Secao 2: estado real apos a carga (sem regressao) ---------------------


def test_loaded_and_failed_routes_preserve_exact_contract():
    """LOADED_ROUTES/FAILED_ROUTES sao consumidos por documentation_service
    (Missao 48), observability (Missao 41-50) e UnifiedCertificationEngine
    (Missao 53) - o contrato (lista de strings / lista de dicts) precisa
    continuar exatamente igual."""
    assert FAILED_ROUTES == []
    assert len(LOADED_ROUTES) == len(ROUTE_MODULES)
    assert all(name.startswith("app.api.routes.") for name in LOADED_ROUTES)


def test_zero_logical_collisions_in_the_real_registered_routes():
    assert ROUTE_COLLISIONS == []


# --- Secao 3: extract_operations() / find_collisions() (unidade pura) -----


def test_extract_operations_combines_outer_prefix_with_router_prefix():
    from fastapi import APIRouter

    router = APIRouter(prefix="/widgets")

    @router.get("/{item_id}")
    def get_widget(item_id: str):
        return {"id": item_id}

    ops = extract_operations(router, prefix="/api/v1")
    assert ("GET", "/api/v1/widgets/{item_id}") in ops


def test_find_collisions_detects_overlap_between_two_different_modules():
    operations_by_module = {
        "app.api.routes.alpha": [("GET", "/api/v1/widgets")],
        "app.api.routes.beta": [("GET", "/api/v1/widgets"), ("POST", "/api/v1/widgets")],
    }

    collisions = find_collisions(operations_by_module)

    assert len(collisions) == 1
    assert collisions[0] == {
        "method": "GET",
        "path": "/api/v1/widgets",
        "first_module": "app.api.routes.alpha",
        "colliding_module": "app.api.routes.beta",
    }


def test_find_collisions_returns_empty_when_there_is_no_overlap():
    operations_by_module = {
        "app.api.routes.alpha": [("GET", "/api/v1/widgets")],
        "app.api.routes.beta": [("GET", "/api/v1/gadgets")],
    }

    assert find_collisions(operations_by_module) == []


def test_find_collisions_does_not_flag_a_module_against_itself():
    operations_by_module = {
        "app.api.routes.alpha": [("GET", "/api/v1/widgets"), ("GET", "/api/v1/widgets")],
    }

    assert find_collisions(operations_by_module) == []


# --- Secao 4: endpoint de diagnostico expoe o novo campo -------------------


def test_diagnostics_routes_endpoint_exposes_collisions_field():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/diagnostics/routes")

    assert response.status_code == 200
    body = response.json()
    assert "loaded" in body and "failed" in body and "collisions" in body
    assert body["collisions"] == []
