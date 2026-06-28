"""Missao 54 - Merge Conflict Prevention.

Esta missao ataca dois pontos de contencao reais, ja documentados, que
geram risco de conflito de merge entre missoes/PRs paralelos:

1. `ROUTE_MODULES`, em `safe_router.py`, era uma lista de ~52 nomes de
   modulo editada a mao por toda missao/PR que adicionasse uma nova
   rota. O `RELATORIO_MISSOES_CLAUDE_41_50_E_CODEX_31_40.md` ja registrou
   um quase-conflito real nessa lista: o Codex inseriu um modulo no fim
   e o Claude inseriu oito no meio, e os dois lados so nao colidiram
   porque calharam de tocar pontos diferentes do arquivo - por
   coincidencia, nao por design. E exatamente a mesma classe de problema
   que a Missao 51 ja resolveu para `config.py` (que tinha 141 campos
   acumulados em um unico arquivo) com `config_domains/` + descoberta
   automatica via `pkgutil`. Esta missao aplica a mesma tecnica aqui:
   `discover_route_modules()` varre `app/api/routes/` e devolve os
   modulos que realmente existem no disco - nenhuma lista central para
   editar, logo nenhum ponto de contencao para colidir.

2. Mesmo sem nenhum conflito textual de Git, dois modulos de rota
   diferentes podem declarar o mesmo metodo HTTP + path por acidente
   (ou por uma fusao de branches feita sem perceber a sobreposicao).
   Isso nunca apareceria como conflito de merge - sao arquivos e linhas
   diferentes - mas produz um bug silencioso: o FastAPI casa rotas na
   ordem de registro, e a segunda rota identica nunca e alcancada por
   nenhuma requisicao. `extract_operations()` + `find_collisions()`
   tornam esse tipo de conflito *logico* visivel (`ROUTE_COLLISIONS`),
   em vez de silencioso.
"""
from __future__ import annotations

from typing import Iterable

import app.api.routes as routes_package


def discover_route_modules() -> list[str]:
    """Nomes (ordenados, deterministicos) de todos os modulos .py em
    app/api/routes/, exceto privados (prefixo "_"). Substitui a antiga
    lista ROUTE_MODULES editada a mao."""
    import pkgutil

    names = [
        module_info.name
        for module_info in pkgutil.iter_modules(routes_package.__path__)
        if not module_info.name.startswith("_")
    ]
    return sorted(names)


def extract_operations(router, prefix: str = "") -> list[tuple[str, str]]:
    """Lista (metodo_http, path_completo) de todas as rotas declaradas
    diretamente em um APIRouter. NAO soma `router.prefix` de novo: o
    FastAPI ja "queima" o prefixo do proprio router em `route.path` no
    momento em que cada `@router.get(...)`/`.post(...)` etc. e declarado
    - somar de novo aqui duplicaria o prefixo (ex.: "/widgets/widgets/1").
    `prefix` representa apenas o prefixo externo de quem vai incluir este
    router (ex.: o "/api/v1" de `api_router`). Usada para detectar colisao
    de metodo+path entre dois modulos de rota diferentes - um tipo de
    conflito que o Git nunca detectaria, porque os dois arquivos em si
    nao tem nenhuma linha em comum."""
    operations: list[tuple[str, str]] = []
    for route in getattr(router, "routes", []):
        methods: Iterable[str] | None = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or path is None:
            continue
        for method in methods:
            operations.append((method, f"{prefix}{path}"))
    return operations


def find_collisions(operations_by_module: dict[str, list[tuple[str, str]]]) -> list[dict]:
    """Dado um mapa {nome_do_modulo: [(metodo, path), ...]}, devolve a
    lista de colisoes: operacoes (metodo+path) registradas por mais de um
    modulo diferente. Funcao pura, testavel isoladamente sem precisar
    montar um FastAPI app real nem importar os ~52 modulos de rota."""
    seen: dict[tuple[str, str], str] = {}
    collisions: list[dict] = []
    for module_name, operations in operations_by_module.items():
        for operation in operations:
            owner = seen.get(operation)
            if owner is not None and owner != module_name:
                method, path = operation
                collisions.append(
                    {
                        "method": method,
                        "path": path,
                        "first_module": owner,
                        "colliding_module": module_name,
                    }
                )
            else:
                seen[operation] = module_name
    return collisions
