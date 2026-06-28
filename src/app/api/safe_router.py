from importlib import import_module

from fastapi import APIRouter

from app.api.route_discovery import discover_route_modules, extract_operations, find_collisions

api_router = APIRouter(prefix="/api/v1")
FAILED_ROUTES = []
LOADED_ROUTES = []
ROUTE_COLLISIONS = []  # Missao 54 - colisao logica de metodo+path entre modulos.

# Missao 54 - Merge Conflict Prevention.
# ROUTE_MODULES deixa de ser uma lista editada a mao (ponto de contencao real,
# ver app/api/route_discovery.py e RELATORIO_MISSOES_CLAUDE_41_50_E_CODEX_31_40.md)
# e passa a ser descoberta automaticamente a partir dos arquivos que existem em
# app/api/routes/. Uma rota nova so precisa existir como arquivo nesse
# diretorio - nenhuma linha a mais para editar em nenhum lugar central.
# M81: inclui automaticamente rotas das missoes 51-59 e 71-80.
ROUTE_MODULES = discover_route_modules()


@api_router.get("/health")
def api_health_check():
    return {
        "status": "ok",
        "scope": "api",
        "loaded_routes": len(LOADED_ROUTES),
        "failed_routes": len(FAILED_ROUTES),
    }


@api_router.get("/diagnostics/routes")
def route_diagnostics():
    return {"loaded": LOADED_ROUTES, "failed": FAILED_ROUTES, "collisions": ROUTE_COLLISIONS}


_operations_by_module: dict[str, list[tuple[str, str]]] = {}

for module_name in ROUTE_MODULES:
    full_name = f"app.api.routes.{module_name}"
    try:
        module = import_module(full_name)
        router = getattr(module, "router", None)
        if router is None:
            FAILED_ROUTES.append({"module": full_name, "error": "router attribute not found"})
            continue
        _operations_by_module[full_name] = extract_operations(router, prefix=api_router.prefix)
        api_router.include_router(router)
        LOADED_ROUTES.append(full_name)
    except Exception as exc:
        FAILED_ROUTES.append({"module": full_name, "error": f"{type(exc).__name__}: {exc}"})

# Missao 54 - detecta, apos carregar todos os modulos, se algum metodo+path
# foi declarado por mais de um modulo. Nunca apareceria como conflito de
# merge no Git (arquivos/linhas diferentes), mas sem este check a segunda
# rota identica fica silenciosamente inalcancavel.
ROUTE_COLLISIONS.extend(find_collisions(_operations_by_module))
