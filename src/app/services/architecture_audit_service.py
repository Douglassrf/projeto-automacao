"""Missao 55 - Continuous Architecture Audit.

Contexto: as Missoes 51, 52 e 54 corrigiram tres pontos de contencao
estruturais reais do repositorio - `config.py` monolitico (M51),
instanciacao inline de service por rota em vez de container de DI (M52), e
`ROUTE_MODULES` hardcoded com colisao logica de rota nao detectada por Git
(M54). Nada impede que uma missao futura - escrita por qualquer agente,
sem ma intencao - reintroduza exatamente o mesmo padrao: um campo novo
direto em `Settings`, uma rota nova fazendo `XService(db)` em vez de
`Depends(...)`, ou `ROUTE_MODULES` reescrito como lista literal "para
simplificar".

Esta missao nao adiciona uma nova correcao estrutural - adiciona o
mecanismo que detecta, de forma continua, quando esses padroes voltam a
aparecer. "Continuo" aqui e literal: nao ha checklist estatico para
atualizar a cada missao nova - o proprio codigo-fonte em disco e a fonte
de verdade, lido via AST a cada chamada. Se uma missao futura reintroduzir
o problema, a proxima chamada a este service ja reporta `clean: False`,
sem precisar editar este arquivo.

Quarto eixo, novo nesta missao: adesao ao container de DI (Missao 52) por
modulo de rota. `registered_providers()` (app/core/container.py) ja
documentava, desde a Missao 52, a intencao de ser consumido por uma
auditoria de arquitetura - este e esse consumidor.

Garantia de leitura pura: nenhum metodo aqui escreve em disco ou no banco -
so le codigo-fonte (arquivos `.py` do proprio repositorio) e estado vivo de
modulos ja importados (`ROUTE_COLLISIONS`, `registered_providers()`).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from app.api.route_discovery import discover_route_modules
from app.core.config import project_root

_SETTINGS_CLASS_NAME = "Settings"
_ROUTE_MODULES_NAME = "ROUTE_MODULES"


def _src_root() -> Path:
    return project_root() / "src"


class ArchitectureAuditService:
    """Missao 55. Le-only - ver garantia de leitura pura na docstring do
    modulo. Nao recebe `db` no construtor porque nenhum dos quatro eixos
    auditados depende de estado de banco (mesma razao pela qual
    `settings_dependency()`, em app/core/container.py, tambem nao usa a
    fabrica generica `provide()`)."""

    # ---- Missao 51: config.py nao pode voltar a declarar campo direto ----

    def audit_config_centralization(self, source: str | None = None) -> dict[str, Any]:
        """Roda live contra app/core/config.py (ou contra `source`, usado
        nos testes para simular uma regressao sem tocar no arquivo real).
        Reprova se a classe `Settings` voltar a ter qualquer `AnnAssign`
        (campo com anotacao de tipo) direto no corpo da classe - exatamente
        o padrao que a Missao 51 eliminou ao mover os 141 campos para
        `config_domains/`."""

        path = _src_root() / "app" / "core" / "config.py"
        text = source if source is not None else path.read_text(encoding="utf-8")
        tree = ast.parse(text)

        hardcoded_fields: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == _SETTINGS_CLASS_NAME:
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        hardcoded_fields.append(item.target.id)

        clean = not hardcoded_fields
        detail = (
            "Settings nao declara nenhum campo direto (composta via build_domain_fields())"
            if clean
            else f"Settings voltou a declarar campo(s) direto(s): {', '.join(hardcoded_fields)}"
        )
        return {"clean": clean, "hardcoded_fields": hardcoded_fields, "detail": detail}

    # ---- Missao 54: ROUTE_MODULES nao pode voltar a ser lista hardcoded ----

    def audit_route_discovery(self, source: str | None = None) -> dict[str, Any]:
        """Roda live contra app/api/safe_router.py (ou contra `source`).
        Reprova se `ROUTE_MODULES` for atribuido a partir de uma lista/tupla
        literal em vez de uma chamada de funcao (`discover_route_modules()`
        ou equivalente) - o padrao hardcoded que a Missao 54 eliminou."""

        path = _src_root() / "app" / "api" / "safe_router.py"
        text = source if source is not None else path.read_text(encoding="utf-8")
        tree = ast.parse(text)

        assigned_via_call = False
        assigned_via_literal = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if _ROUTE_MODULES_NAME not in target_names:
                    continue
                if isinstance(node.value, ast.Call):
                    assigned_via_call = True
                elif isinstance(node.value, (ast.List, ast.Tuple)):
                    assigned_via_literal = True

        clean = assigned_via_call and not assigned_via_literal
        if clean:
            detail = "ROUTE_MODULES e atribuido a partir de uma chamada (descoberta automatica)"
        elif assigned_via_literal:
            detail = "ROUTE_MODULES voltou a ser uma lista/tupla literal hardcoded"
        else:
            detail = "ROUTE_MODULES nao encontrado em safe_router.py"
        return {"clean": clean, "detail": detail}

    # ---- Missao 54: colisao logica de rota, lida em tempo real ----

    def audit_route_collisions(self) -> dict[str, Any]:
        """Reusa `ROUTE_COLLISIONS`, calculada ao vivo por safe_router.py a
        partir das rotas de fato registradas - nao recalcula a logica de
        colisao aqui (ja existe e ja tem suite propria na Missao 54)."""

        from app.api.safe_router import ROUTE_COLLISIONS

        collisions = list(ROUTE_COLLISIONS)
        return {
            "clean": len(collisions) == 0,
            "collision_count": len(collisions),
            "collisions": collisions,
        }

    # ---- Missao 52: adesao ao container de DI, modulo por modulo ----

    def audit_di_adoption(self) -> dict[str, Any]:
        """Para cada modulo em app/api/routes/ (mesma lista que
        `discover_route_modules()` usa para registrar rotas), classifica via
        AST: `via_container` (importa `app.core.container`, ou seja, usa
        `Depends(get_xxx_service)`), `raw_instantiation` (faz `XxxService(db)`
        direto, sem container) ou `neither` (nao detectou nenhum dos dois
        padroes). Nao e pass/fail - adesao ao container e incremental por
        natureza (ver comentario em container.py "adesao por rota e
        incremental") - este eixo e informativo, nao bloqueia `audit()`."""

        modules = discover_route_modules()
        routes_dir = _src_root() / "app" / "api" / "routes"

        via_container: list[str] = []
        raw_instantiation: list[str] = []
        neither: list[str] = []

        for name in modules:
            file_path = routes_dir / f"{name}.py"
            if not file_path.exists():
                neither.append(name)
                continue

            text = file_path.read_text(encoding="utf-8")
            tree = ast.parse(text)

            imports_container = any(
                isinstance(node, ast.ImportFrom) and node.module == "app.core.container"
                for node in ast.walk(tree)
            )
            has_raw_service_call = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id.endswith("Service")
                for node in ast.walk(tree)
            )

            if imports_container:
                via_container.append(name)
            elif has_raw_service_call:
                raw_instantiation.append(name)
            else:
                neither.append(name)

        total = len(modules)
        adoption_rate = round(len(via_container) / total, 4) if total else 0.0

        return {
            "total_route_modules": total,
            "via_container": sorted(via_container),
            "raw_instantiation": sorted(raw_instantiation),
            "neither": sorted(neither),
            "adoption_rate": adoption_rate,
            "registered_providers": self._registered_providers(),
        }

    @staticmethod
    def _registered_providers() -> list[str]:
        """Import tardio (dentro do metodo, nao no topo do modulo) de
        proposito: `app.core.container` importa `ArchitectureAuditService`
        para registrar `get_architecture_audit_service` - importar
        `registered_providers` no topo deste arquivo criaria import
        circular entre os dois modulos. Mesmo padrao ja usado em
        `unified_certification_service.py` (`_check_apis`) para evitar
        circular import com `safe_router`."""
        from app.core.container import registered_providers

        return registered_providers()

    # ---- agregado ----

    def audit(self) -> dict[str, Any]:
        """Roda os quatro eixos agora, contra o estado real do repositorio.
        `clean` agrega apenas os tres eixos pass/fail (config, rotas,
        colisoes) - adesao a DI e informativa, conforme documentado em
        `audit_di_adoption()`."""

        config_check = self.audit_config_centralization()
        routing_check = self.audit_route_discovery()
        collisions_check = self.audit_route_collisions()
        di_check = self.audit_di_adoption()

        overall_clean = config_check["clean"] and routing_check["clean"] and collisions_check["clean"]

        return {
            "clean": overall_clean,
            "config_centralization": config_check,
            "route_discovery": routing_check,
            "route_collisions": collisions_check,
            "di_adoption": di_check,
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        """Renderiza `audit()` (ou um `report` ja calculado) como Markdown
        legivel por humano."""

        report = report if report is not None else self.audit()
        di = report["di_adoption"]

        lines: list[str] = []
        verdict = "ARQUITETURA LIMPA" if report["clean"] else "DESVIO ESTRUTURAL DETECTADO"
        lines.append(f"# Auditoria Continua de Arquitetura - {verdict}")
        lines.append("")
        lines.append(f"- Config centralizada (Missao 51): {report['config_centralization']['detail']}")
        lines.append(f"- Descoberta de rotas (Missao 54): {report['route_discovery']['detail']}")
        lines.append(f"- Colisoes logicas de rota: {report['route_collisions']['collision_count']}")
        lines.append(
            f"- Adesao ao container de DI (Missao 52): {len(di['via_container'])}/{di['total_route_modules']} "
            f"modulos ({di['adoption_rate']:.1%}) - via container: {', '.join(di['via_container']) or 'nenhum'}"
        )
        return "\n".join(lines)
