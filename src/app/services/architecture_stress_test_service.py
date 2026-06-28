"""Missao 59 - Architecture Stress Test.

Contexto: as Missoes 51-58 entregaram oito pecas de arquitetura - todas
desenhadas, desde o inicio, para nunca guardar snapshot estatico: cada
chamada rele o estado real (dominios de config, container de DI,
descoberta de rotas, auditoria continua, revisao de codigo via AST,
dashboard de evolucao via mineracao de git, gestor de divida tecnica).
Nenhuma delas, porem, foi verificada sob **concorrencia real** - um bug
de estado compartilhado (ex.: um dict de modulo mutado por engano, uma
lista global reaproveitada entre chamadas, um service que silenciosamente
guarda cache entre requisicoes) so apareceria sob carga concorrente,
nunca num teste sequencial isolado, que e exatamente o formato de toda a
suite hoje.

**Isto nao e a Missao 27A** (`load_test_mission27a.py`, ja existente no
repositorio): aquele teste de carga estressa o **caminho de negocio**
(campanhas, agente de IA, cobertura de trace header) com lotes
configuraveis e metricas de SLA. Esta missao estressa especificamente a
**camada de arquitetura** criada pelas Missoes 51-58 - dispara N chamadas
concorrentes contra os 5 endpoints "live" dessas missoes e verifica tres
coisas que nenhum teste sequencial prova:

1. **Zero falha sob concorrencia** - nenhuma excecao, nenhum status
   diferente de 200, em nenhuma das chamadas paralelas.
2. **Consistencia de payload** - todas as respostas concorrentes para o
   mesmo endpoint trazem a mesma "assinatura" central (prova ausencia de
   race condition de estado compartilhado, dado que o repositorio real
   nao muda durante o burst de um teste).
3. **Isolamento do container de DI (Missao 52)** - chamar
   `get_tech_debt_manager_service()` N vezes em sequencia rapida sempre
   devolve instancias **distintas**; uma instancia compartilhada por
   acidente esconderia bugs de estado acumulado entre requisicoes
   diferentes, que so se manifestam com mais de um "cliente" em jogo.

Tudo via `TestClient` in-process (mesmo padrao de concorrencia -
`ThreadPoolExecutor` - ja usado pela Missao 27A) - nenhuma carga de rede
real, nenhum servico externo, conforme a regra 6 do CLAUDE.md.
"""

from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from fastapi.testclient import TestClient

ClientFactory = Callable[[], TestClient]

# Os 5 endpoints "live" entregues pelas Missoes 53/55/56/57/58 - somente a
# camada de arquitetura desta serie, nenhum endpoint de negocio (esses ja
# sao cobertos pela Missao 27A).
STRESS_TARGETS: tuple[tuple[str, str], ...] = (
    ("unified_certification", "/api/v1/certification/unified/live"),
    ("architecture_audit", "/api/v1/architecture-audit/live"),
    ("code_review", "/api/v1/code-review/live"),
    ("evolution_dashboard", "/api/v1/evolution-dashboard/live"),
    ("tech_debt_manager", "/api/v1/tech-debt/live"),
)

# Campos usados para o teste de consistencia por endpoint - devem ser
# identicos entre chamadas concorrentes, dado que o repositorio real nao
# muda durante o burst.
_CONSISTENCY_KEYS: dict[str, tuple[str, ...]] = {
    "unified_certification": ("unified_certified",),
    "architecture_audit": ("clean",),
    "code_review": ("clean", "total_files_scanned"),
    "tech_debt_manager": ("summary",),
}


def _make_hashable(value: Any) -> Any:
    """Converte dict/list (nao hashable, nao cabem num `set`) em tuplas
    aninhadas - necessario porque o payload de alguns endpoints (ex.:
    `tech_debt_manager`'s `summary`, um dict) precisa entrar num `set` de
    assinaturas para o teste de consistencia."""
    if isinstance(value, dict):
        return tuple(sorted((key, _make_hashable(val)) for key, val in value.items()))
    if isinstance(value, list):
        return tuple(_make_hashable(item) for item in value)
    return value


def _percentile(values: list[float], pct: float) -> float:
    """Percentil simples por indice ordenado - mesma logica usada em
    `load_test_mission27a.py`, sem dependencia de bibliotecas externas
    de estatistica alem do `statistics` padrao."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = max(0, min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1)))))
    return ordered[index]


class ArchitectureStressTestService:
    """Missao 59. Leitura/execucao apenas - dispara requisicoes
    in-process contra endpoints ja existentes das Missoes 53/55/56/57/58
    e contra o container da Missao 52; nunca contra rede real, nunca
    contra servico externo. Nao certifica nada por conta propria (nao tem
    eixo `clean` proprio que vire bloqueante para outro motor) - so
    reporta comportamento observado sob concorrencia."""

    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self.client_factory = client_factory or self._default_client_factory()

    @staticmethod
    def _default_client_factory() -> ClientFactory:
        from app.main import app as real_app

        def _make_started_client() -> TestClient:
            # Correcao pos-commit desta missao: um `TestClient` "cru"
            # (sem `__enter__`) so monta seu transporte/portal ASGI de
            # forma lazy na primeira requisicao. Quando duas threads
            # disparam a primeira requisicao concorrentemente contra um
            # cliente assim, essa montagem lazy corre uma contra a outra
            # e uma das duas pode receber 404 - reproduzido isolando a
            # causa (cliente "cru" compartilhado -> falha intermitente
            # rotativa entre os 5 endpoints; `with TestClient(app) as
            # client:` mesmo cliente -> zero falha em repeticao).
            # `__enter__()` forca a montagem do portal/lifespan uma unica
            # vez, de forma sequencial, antes de qualquer uso concorrente.
            client = TestClient(real_app)
            client.__enter__()
            return client

        return _make_started_client

    def _burst(self, path: str, requests: int, concurrency: int) -> list[dict[str, Any]]:
        """Dispara `requests` chamadas GET contra `path`, no maximo
        `concurrency` simultaneas, via `ThreadPoolExecutor` - mesmo
        idioma de concorrencia da Missao 27A. Um unico cliente por burst,
        compartilhado entre as threads concorrentes - seguro porque o
        cliente real ja vem com o portal ASGI montado (ver
        `_default_client_factory`)."""
        client = self.client_factory()

        def _one(_: int) -> dict[str, Any]:
            start = time.perf_counter()
            response = client.get(path)
            elapsed_ms = (time.perf_counter() - start) * 1000
            body: Any = None
            if response.status_code == 200:
                try:
                    body = response.json()
                except ValueError:
                    body = None
            return {
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "body": body,
            }

        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
            futures = [executor.submit(_one, i) for i in range(requests)]
            for future in as_completed(futures):
                results.append(future.result())
        return results

    @staticmethod
    def _extract_signature(name: str, body: Any) -> Any:
        """Extrai os campos centrais que devem ser identicos entre
        chamadas concorrentes (ver `_CONSISTENCY_KEYS`). Para o dashboard
        de evolucao, usa os contadores de saude da timeline (Missao 57),
        que nao mudam durante o burst."""
        if not isinstance(body, dict):
            return None
        if name == "evolution_dashboard":
            timeline_health = body.get("timeline_health")
            if not isinstance(timeline_health, dict):
                return None
            return (
                timeline_health.get("total_missions_detected"),
                _make_hashable(timeline_health.get("missing_mission_numbers", [])),
                _make_hashable(timeline_health.get("duplicate_mission_numbers", [])),
            )
        keys = _CONSISTENCY_KEYS.get(name, ())
        return tuple(_make_hashable(body.get(key)) for key in keys)

    def stress_endpoint(
        self, name: str, path: str, requests: int = 4, concurrency: int = 2
    ) -> dict[str, Any]:
        """Dispara o burst contra um unico endpoint e resume falhas,
        latencia (p50/p95/max, mesma convencao de metrica da Missao
        27A) e consistencia de payload entre as respostas."""
        results = self._burst(path, requests=requests, concurrency=concurrency)
        latencies = [r["elapsed_ms"] for r in results]
        failures = [r for r in results if r["status_code"] != 200]
        signatures = {
            self._extract_signature(name, r["body"])
            for r in results
            if r["status_code"] == 200
        }
        return {
            "name": name,
            "path": path,
            "total_requests": len(results),
            "failed_requests": len(failures),
            "error_rate_percent": (
                round(100 * len(failures) / len(results), 2) if results else 0.0
            ),
            "latency_ms": {
                "p50": round(_percentile(latencies, 50), 2),
                "p95": round(_percentile(latencies, 95), 2),
                "max": round(max(latencies), 2) if latencies else 0.0,
                "mean": round(statistics.fmean(latencies), 2) if latencies else 0.0,
            },
            "distinct_payload_signatures": len(signatures),
            "consistent": len(signatures) <= 1,
        }

    def stress_container_isolation(self, calls: int = 4) -> dict[str, Any]:
        """Chama `get_tech_debt_manager_service()` (Missao 58, fabrica
        sem `db`, mesmo padrao hand-written de M55/M56) `calls` vezes em
        sequencia rapida e confirma que cada chamada devolve uma
        instancia **distinta** - prova direta de que o container (Missao
        52) nunca esconde estado compartilhado entre "requisicoes"."""
        from app.core.container import get_tech_debt_manager_service

        instances = [get_tech_debt_manager_service() for _ in range(max(1, calls))]
        distinct_ids = {id(instance) for instance in instances}
        return {
            "calls": len(instances),
            "distinct_instances": len(distinct_ids),
            "shares_no_instance": len(distinct_ids) == len(instances),
        }

    def stress_report(self, requests: int = 4, concurrency: int = 2) -> dict[str, Any]:
        """Agrega o burst dos 5 endpoints de arquitetura + o teste de
        isolamento do container num unico payload, com veredito `clean`
        proprio desta missao (independente de Unified/architecture-audit/
        code-review - nao reescreve nenhum deles)."""
        endpoints = [
            self.stress_endpoint(name, path, requests=requests, concurrency=concurrency)
            for name, path in STRESS_TARGETS
        ]
        container = self.stress_container_isolation(calls=requests)
        clean = (
            all(endpoint["failed_requests"] == 0 for endpoint in endpoints)
            and all(endpoint["consistent"] for endpoint in endpoints)
            and container["shares_no_instance"]
        )
        return {
            "clean": clean,
            "requests_per_endpoint": requests,
            "concurrency": concurrency,
            "endpoints": endpoints,
            "container_isolation": container,
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        """Relatorio legivel em portugues, mesma convencao de
        `/certification/markdown`, `/architecture-audit/markdown`,
        `/code-review/markdown`, `/evolution-dashboard/markdown`,
        `/tech-debt/markdown`."""
        report = report if report is not None else self.stress_report()
        verdict = "OK" if report["clean"] else "DESVIO"
        lines: list[str] = [
            "# Teste de Estresse de Arquitetura",
            "",
            f"- Veredito: {verdict}",
            (
                f"- Carga: {report['requests_per_endpoint']} requisicoes por "
                f"endpoint, concorrencia {report['concurrency']}"
            ),
            "",
            "## Endpoints sob concorrencia",
        ]
        for endpoint in report["endpoints"]:
            status = "consistente" if endpoint["consistent"] else "INCONSISTENTE"
            lines.append(
                f"- {endpoint['name']} ({endpoint['path']}): "
                f"{endpoint['total_requests']} requisicoes, "
                f"{endpoint['failed_requests']} falha(s), "
                f"p95 {endpoint['latency_ms']['p95']}ms, {status}"
            )
        container = report["container_isolation"]
        isolation = (
            "sem estado compartilhado"
            if container["shares_no_instance"]
            else "ESTADO COMPARTILHADO DETECTADO"
        )
        lines.append("")
        lines.append("## Isolamento do container de DI (Missao 52)")
        lines.append(
            f"- {container['calls']} chamadas, {container['distinct_instances']} "
            f"instancia(s) distinta(s) - {isolation}"
        )
        return "\n".join(lines)
