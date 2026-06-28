"""Missao 59 - Architecture Stress Test. Suite dedicada."""

from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from app.core.container import get_architecture_stress_test_service, registered_providers
from app.main import app as real_app
from app.services.architecture_stress_test_service import (
    STRESS_TARGETS,
    ArchitectureStressTestService,
    _make_hashable,
    _percentile,
)


def _service(client_factory=None) -> ArchitectureStressTestService:
    return ArchitectureStressTestService(client_factory=client_factory)


class _FakeResponse:
    """Substitui a resposta do `TestClient` - mesma logica de fake usada
    para isolar `CodeReviewService`/`EvolutionDashboardService` das
    Missoes 56/57: nenhuma chamada HTTP real, controle total do
    status/payload devolvido."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, responder):
        self._responder = responder

    def get(self, path):
        return self._responder(path)


def _fixed_client_factory(status_code, payload):
    return lambda: _FakeClient(lambda path: _FakeResponse(status_code, payload))


_HEALTHY_PAYLOAD = {
    "unified_certified": True,
    "clean": True,
    "total_files_scanned": 1,
    "summary": {"total_debt_items": 1},
    "timeline_health": {
        "total_missions_detected": 1,
        "missing_mission_numbers": [],
        "duplicate_mission_numbers": [],
    },
}


# --- _percentile ---------------------------------------------------------------------

def test_percentile_handles_empty_list_without_crashing():
    assert _percentile([], 95) == 0.0


def test_percentile_p50_of_simple_list_is_the_median():
    assert _percentile([10, 20, 30, 40, 50], 50) == 30


def test_percentile_p95_is_near_the_top_of_the_distribution():
    values = list(range(1, 101))
    assert 90 <= _percentile(values, 95) <= 100


# --- _make_hashable (regressao do bug encontrado nesta missao) -----------------------

def test_make_hashable_converts_dict_into_a_sortable_tuple():
    result = _make_hashable({"b": 2, "a": 1})
    assert result == (("a", 1), ("b", 2))
    hash(result)


def test_make_hashable_converts_nested_list_and_dict_recursively():
    result = _make_hashable({"items": [1, {"x": 2}]})
    hash(result)


def test_make_hashable_leaves_plain_scalars_untouched():
    assert _make_hashable(42) == 42
    assert _make_hashable("clean") == "clean"
    assert _make_hashable(None) is None


# --- STRESS_TARGETS --------------------------------------------------------------------

def test_stress_targets_covers_exactly_the_five_architecture_live_endpoints():
    names = {name for name, _ in STRESS_TARGETS}
    assert names == {
        "unified_certification",
        "architecture_audit",
        "code_review",
        "evolution_dashboard",
        "tech_debt_manager",
    }


def test_stress_targets_never_includes_the_mission27a_business_endpoint():
    """M59 e distinta da M27A (load_test_mission27a.py): aquela estressa
    o caminho de negocio (campanhas/IA); esta estressa a camada de
    arquitetura das Missoes 51-58. Nenhum path deveria escapar de
    /api/v1/ nem citar rotas de negocio."""
    paths = {path for _, path in STRESS_TARGETS}
    for path in paths:
        assert path.startswith("/api/v1/")
    assert not any("campaign" in p or "agent" in p or "mission-27a" in p for p in paths)


# --- _extract_signature ------------------------------------------------------------------

def test_extract_signature_returns_none_when_body_is_not_a_dict():
    assert ArchitectureStressTestService._extract_signature("unified_certification", None) is None


def test_extract_signature_combines_multiple_keys_for_code_review():
    body = {"clean": True, "total_files_scanned": 249}
    assert ArchitectureStressTestService._extract_signature("code_review", body) == (True, 249)


def test_extract_signature_evolution_dashboard_returns_none_when_timeline_health_missing():
    assert ArchitectureStressTestService._extract_signature("evolution_dashboard", {"foo": "bar"}) is None


# --- stress_endpoint (fakes, sem rede real) -----------------------------------------------

def test_stress_endpoint_reports_zero_failures_and_non_negative_latency_when_all_responses_are_200():
    service = _service(client_factory=_fixed_client_factory(200, {"clean": True}))
    result = service.stress_endpoint(
        "architecture_audit", "/api/v1/architecture-audit/live", requests=4, concurrency=2
    )
    assert result["total_requests"] == 4
    assert result["failed_requests"] == 0
    assert result["error_rate_percent"] == 0.0
    assert result["latency_ms"]["p50"] >= 0
    assert result["latency_ms"]["p95"] >= 0
    assert result["latency_ms"]["mean"] >= 0
    assert result["distinct_payload_signatures"] == 1
    assert result["consistent"] is True


def test_stress_endpoint_reports_failures_when_some_responses_are_non_200():
    counter = {"n": 0}
    lock = threading.Lock()

    def responder(path):
        with lock:
            counter["n"] += 1
            n = counter["n"]
        status = 500 if n % 2 == 0 else 200
        return _FakeResponse(status, {"clean": True})

    service = _service(client_factory=lambda: _FakeClient(responder))
    result = service.stress_endpoint(
        "architecture_audit", "/api/v1/architecture-audit/live", requests=4, concurrency=1
    )
    assert result["failed_requests"] == 2
    assert result["error_rate_percent"] == 50.0


def test_stress_endpoint_flags_inconsistent_when_payload_signature_diverges():
    counter = {"n": 0}
    lock = threading.Lock()

    def responder(path):
        with lock:
            counter["n"] += 1
            n = counter["n"]
        return _FakeResponse(200, {"clean": n != 2})

    service = _service(client_factory=lambda: _FakeClient(responder))
    result = service.stress_endpoint(
        "architecture_audit", "/api/v1/architecture-audit/live", requests=4, concurrency=1
    )
    assert result["consistent"] is False
    assert result["distinct_payload_signatures"] == 2


def test_stress_endpoint_handles_unhashable_dict_payload_field_without_crashing():
    """Regressao direta do bug encontrado e corrigido nesta missao: o
    campo `summary` do tech_debt_manager e um dict e foi colocado num
    `set` de assinaturas sem conversao - `TypeError: unhashable type:
    'dict'`, reproduzido ao vivo contra o app real antes da correcao."""
    payload = {"summary": {"total_debt_items": 3, "items_by_rule": {"todo_marker": 1}}}
    service = _service(client_factory=_fixed_client_factory(200, payload))
    result = service.stress_endpoint(
        "tech_debt_manager", "/api/v1/tech-debt/live", requests=4, concurrency=2
    )
    assert result["consistent"] is True
    assert result["distinct_payload_signatures"] == 1


def test_stress_endpoint_handles_zero_requests_without_crashing():
    service = _service(client_factory=_fixed_client_factory(200, {"clean": True}))
    result = service.stress_endpoint(
        "architecture_audit", "/api/v1/architecture-audit/live", requests=0, concurrency=2
    )
    assert result["total_requests"] == 0
    assert result["failed_requests"] == 0
    assert result["error_rate_percent"] == 0.0
    assert result["consistent"] is True


# --- stress_container_isolation -----------------------------------------------------------

def test_stress_container_isolation_returns_distinct_instances_for_the_real_container():
    service = _service()
    result = service.stress_container_isolation(calls=4)
    assert result["calls"] == 4
    assert result["distinct_instances"] == 4
    assert result["shares_no_instance"] is True


def test_stress_container_isolation_detects_a_synthetic_shared_instance(monkeypatch):
    """Prova que o teste de isolamento realmente detectaria o bug que se
    propoe a prevenir - mesmo espirito das regressoes sinteticas das
    Missoes 55/57 (flags_a_hardcoded_field/..._detects_a_synthetic_gap)."""
    shared = object()
    monkeypatch.setattr("app.core.container.get_tech_debt_manager_service", lambda: shared)
    service = _service()
    result = service.stress_container_isolation(calls=4)
    assert result["distinct_instances"] == 1
    assert result["shares_no_instance"] is False


# --- stress_report ---------------------------------------------------------------------------

def test_stress_report_combines_all_five_targets_and_the_container_check():
    service = _service(client_factory=_fixed_client_factory(200, _HEALTHY_PAYLOAD))
    report = service.stress_report(requests=4, concurrency=2)
    names = {ep["name"] for ep in report["endpoints"]}
    assert names == {name for name, _ in STRESS_TARGETS}
    assert "container_isolation" in report
    assert report["requests_per_endpoint"] == 4
    assert report["concurrency"] == 2


def test_stress_report_clean_is_true_when_every_endpoint_is_healthy():
    service = _service(client_factory=_fixed_client_factory(200, _HEALTHY_PAYLOAD))
    report = service.stress_report(requests=4, concurrency=2)
    assert report["clean"] is True


def test_stress_report_clean_is_false_when_any_endpoint_has_failures():
    def responder(path):
        if "tech-debt" in path:
            return _FakeResponse(500, {})
        return _FakeResponse(200, _HEALTHY_PAYLOAD)

    service = _service(client_factory=lambda: _FakeClient(responder))
    report = service.stress_report(requests=4, concurrency=2)
    assert report["clean"] is False


def test_stress_report_clean_is_false_when_container_isolation_fails(monkeypatch):
    service = _service(client_factory=_fixed_client_factory(200, _HEALTHY_PAYLOAD))
    monkeypatch.setattr(
        service,
        "stress_container_isolation",
        lambda calls=4: {"calls": calls, "distinct_instances": 1, "shares_no_instance": False},
    )
    report = service.stress_report(requests=4, concurrency=2)
    assert report["clean"] is False


# --- render_markdown ---------------------------------------------------------------------------

def test_render_markdown_mentions_ok_verdict_when_clean():
    service = _service(client_factory=_fixed_client_factory(200, _HEALTHY_PAYLOAD))
    report = service.stress_report(requests=4, concurrency=2)
    markdown = service.render_markdown(report)
    assert "Teste de Estresse de Arquitetura" in markdown
    assert "Veredito: OK" in markdown


def test_render_markdown_mentions_desvio_verdict_when_not_clean():
    service = _service(client_factory=_fixed_client_factory(500, {}))
    report = service.stress_report(requests=4, concurrency=2)
    markdown = service.render_markdown(report)
    assert "Veredito: DESVIO" in markdown


# --- Container (Missao 52) e endpoints HTTP --------------------------------------------------

def test_architecture_stress_test_service_itself_is_not_in_the_provider_registry():
    """Mesma decisao documentada nas Missoes 55/56/58: services sem `db`
    nao usam `provide()`, por isso nao aparecem em `registered_providers()`."""
    assert "ArchitectureStressTestService" not in registered_providers()


def test_architecture_stress_test_live_endpoint_returns_real_computed_report():
    client = TestClient(real_app)
    response = client.get("/api/v1/architecture-stress-test/live")
    assert response.status_code == 200
    payload = response.json()
    assert "clean" in payload
    assert len(payload["endpoints"]) == 5
    assert "container_isolation" in payload


def test_architecture_stress_test_markdown_endpoint_returns_text():
    class _FakeStressTest:
        def render_markdown(self):
            return "# Teste de Estresse de Arquitetura\n\n- Veredito: OK"

    real_app.dependency_overrides[get_architecture_stress_test_service] = lambda: _FakeStressTest()
    try:
        client = TestClient(real_app)
        response = client.get("/api/v1/architecture-stress-test/markdown")
        assert response.status_code == 200
        assert "Teste de Estresse de Arquitetura" in response.text
    finally:
        real_app.dependency_overrides.pop(get_architecture_stress_test_service, None)


def test_architecture_stress_test_endpoint_is_overridable_via_container_not_hardcoded():
    class _FakeStressTest:
        def stress_report(self):
            return {
                "clean": True,
                "requests_per_endpoint": 0,
                "concurrency": 0,
                "endpoints": [],
                "container_isolation": {},
            }

    real_app.dependency_overrides[get_architecture_stress_test_service] = lambda: _FakeStressTest()
    try:
        client = TestClient(real_app)
        response = client.get("/api/v1/architecture-stress-test/live")
        assert response.status_code == 200
        assert response.json()["endpoints"] == []
    finally:
        real_app.dependency_overrides.pop(get_architecture_stress_test_service, None)
