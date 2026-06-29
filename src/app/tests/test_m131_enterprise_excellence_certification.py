"""Missao 131 - Enterprise Excellence Certification (capstone da Fase v2.1).

Cobertura:
1. Cada uma das 12 dimensoes isolada, usando fakes com contador de
   chamadas - prova de reuso direto das Missoes 42/47/48/49/56/57/58/
   122/123/124/127, nunca reimplementacao.
2. `_SingleFlightStressTest` - a memoizacao que evita pagar o teste de
   carga real (Missao 59) duas vezes quando `quality_observatory` e
   `council` sao ambos construidos por este servico (ver docstring do
   modulo). Testada diretamente com um motor falso instrumentado.
3. As 5 criterios de aprovacao do briefing, cada um testado nas suas
   fronteiras reais - incluindo a prova explicita de que
   `aprovacao_conselho_tecnico` consome `council.council_review()`
   (so "desfavoravel" bloqueia).
4. Politica de seguranca ESTRITA desta missao (diferente da politica
   leniente das Missoes 124/130) - testada explicitamente.
5. `render_markdown()` - certificada e nao certificada, incluindo o
   aviso de heuristica.
6. Teste contra o repositorio real (sem mocks) para as 10 dimensoes
   baratas - smoke test honesto, sem disparar o teste de carga real
   (ver nota de custo no docstring do modulo sobre o limite do
   sandbox de execucao).
7. Registro real via `provide()` no container (esta missao TEM banco,
   mesmo padrao das Missoes 124/125/126/130).
8. Endpoints HTTP `/live` e `/markdown` via stub - mesma razao da
   Missao 130 (evitar disparar o teste de carga real so para provar
   fiacao HTTP, ja coberto por evidencia em separado).
"""

from __future__ import annotations

from app.core.container import (
    get_enterprise_excellence_certification_service,
    registered_providers,
)
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.enterprise_excellence_certification_service import (
    EnterpriseExcellenceCertificationService,
    _SingleFlightStressTest,
)
from fastapi.testclient import TestClient


def _service(**kwargs) -> EnterpriseExcellenceCertificationService:
    db = SessionLocal()
    return EnterpriseExcellenceCertificationService(db, **kwargs)


# --- fakes --------------------------------------------------------------


class _FakeArchitectureScoring:
    def __init__(self, classification: str = "healthy", overall_score: float = 80.0, attention: list[str] | None = None) -> None:
        self._classification = classification
        self._overall_score = overall_score
        self._attention = attention or []
        self.calls = 0

    def score_report(self) -> dict:
        self.calls += 1
        return {
            "overall_score": self._overall_score,
            "overall_classification": self._classification,
            "attention_dimensions": self._attention,
        }


class _FakeEvolutionDashboard:
    def __init__(
        self,
        unified_certified: bool = True,
        platinum: bool = True,
        gold: bool = True,
        code_review_clean: bool = True,
        blocking_findings: int = 0,
    ) -> None:
        self._unified_certified = unified_certified
        self._platinum = platinum
        self._gold = gold
        self._code_review_clean = code_review_clean
        self._blocking_findings = blocking_findings
        self.calls = 0

    def current_snapshot(self) -> dict:
        self.calls += 1
        return {
            "unified_certified": self._unified_certified,
            "platinum_certified": self._platinum,
            "gold_certified": self._gold,
            "code_review_clean": self._code_review_clean,
            "code_review_blocking_findings": self._blocking_findings,
        }


class _FakeDependencyAudit:
    def __init__(self, missing_count: int = 0, version_mismatch_count: int = 0, unpinned_count: int = 0) -> None:
        self._missing_count = missing_count
        self._version_mismatch_count = version_mismatch_count
        self._unpinned_count = unpinned_count
        self.calls = 0

    def audit(self) -> dict:
        self.calls += 1
        return {
            "missing_count": self._missing_count,
            "version_mismatch_count": self._version_mismatch_count,
            "unpinned_count": self._unpinned_count,
        }


class _FakeQualityObservatory:
    def __init__(self, perf_healthy: bool = True, perf_value: bool = True, unhealthy_dimensions: list[str] | None = None) -> None:
        self._perf_healthy = perf_healthy
        self._perf_value = perf_value
        self._unhealthy_dimensions = unhealthy_dimensions or []
        self.calls = 0

    def quality_report(self) -> dict:
        self.calls += 1
        return {
            "monitored_dimensions": {
                "performance": {"healthy": self._perf_healthy, "value": self._perf_value},
            },
            "unhealthy_dimensions": self._unhealthy_dimensions,
        }


class _FakeRecovery:
    def __init__(self, healthy: bool = True, warnings: list[str] | None = None, recoverable_now: int = 0, requires_external_action: int = 0) -> None:
        self._healthy = healthy
        self._warnings = warnings or []
        self._recoverable_now = recoverable_now
        self._requires_external_action = requires_external_action
        self.calls = 0

    def recovery_report(self) -> dict:
        self.calls += 1
        return {
            "healthy": self._healthy,
            "warnings": self._warnings,
            "recoverable_now": self._recoverable_now,
            "requires_external_action": self._requires_external_action,
        }


class _FakeQueue:
    def __init__(self, healthy: bool = True, warnings: list[str] | None = None) -> None:
        self._healthy = healthy
        self._warnings = warnings or []
        self.calls = 0

    def health_report(self) -> dict:
        self.calls += 1
        return {"healthy": self._healthy, "warnings": self._warnings}


class _FakeDocumentation:
    def __init__(self, failed: int = 0, settings_issues: list[str] | None = None) -> None:
        self._failed = failed
        self._settings_issues = settings_issues or []
        self.calls = 0

    def live_snapshot(self) -> dict:
        self.calls += 1
        return {"routes": {"failed": self._failed}, "settings_issues": self._settings_issues}


class _FakeEvolutionTimeline:
    def __init__(self, gaps: int = 0) -> None:
        self._gaps = gaps
        self.calls = 0

    def evolution_report(self) -> dict:
        self.calls += 1
        return {
            "module_evolution": {"files_without_history": ["x"] * self._gaps},
            "api_evolution": {"files_without_history": []},
            "service_evolution": {"files_without_history": []},
        }


class _FakeMemoryCore:
    def __init__(self, mission_count: int = 10, decisions: int = 5, incidents: int = 2) -> None:
        self._mission_count = mission_count
        self._decisions = decisions
        self._incidents = incidents
        self.calls = 0

    def memory_report(self) -> dict:
        self.calls += 1
        return {
            "mission_history": list(range(self._mission_count)),
            "architectural_decision_history": list(range(self._decisions)),
            "incident_history": list(range(self._incidents)),
        }


class _FakeTechDebtManager:
    def __init__(self, total_items: int = 10, files_with_debt: int = 5, total_priority_score: int = 50) -> None:
        self._total_items = total_items
        self._files_with_debt = files_with_debt
        self._total_priority_score = total_priority_score
        self.calls = 0

    def debt_report(self) -> dict:
        self.calls += 1
        return {
            "summary": {
                "total_debt_items": self._total_items,
                "files_with_debt": self._files_with_debt,
                "total_priority_score": self._total_priority_score,
            }
        }


class _FakeCouncil:
    def __init__(self, recommendation: str = "favoravel", concern_domains: list[str] | None = None, supportive_domains: list[str] | None = None) -> None:
        self._recommendation = recommendation
        self._concern_domains = concern_domains or []
        self._supportive_domains = supportive_domains or []
        self.calls = 0

    def council_review(self) -> dict:
        self.calls += 1
        return {
            "recommendation": self._recommendation,
            "concern_domains": self._concern_domains,
            "supportive_domains": self._supportive_domains,
        }


def _all_healthy_fakes() -> dict:
    return {
        "architecture_scoring": _FakeArchitectureScoring(),
        "evolution_dashboard": _FakeEvolutionDashboard(),
        "dependency_audit": _FakeDependencyAudit(),
        "quality_observatory": _FakeQualityObservatory(),
        "recovery_service": _FakeRecovery(),
        "queue_service": _FakeQueue(),
        "documentation": _FakeDocumentation(),
        "evolution_timeline": _FakeEvolutionTimeline(),
        "memory_core": _FakeMemoryCore(),
        "tech_debt_manager": _FakeTechDebtManager(),
        "council": _FakeCouncil(),
    }


# --- _SingleFlightStressTest (a correcao da chamada dupla) -------------------


def test_single_flight_stress_test_caches_after_first_real_call():
    calls = {"n": 0}

    class _CountingEngine:
        def stress_report(self):
            calls["n"] += 1
            return {"clean": True, "n": calls["n"]}

    shim = _SingleFlightStressTest(_CountingEngine())
    first = shim.stress_report()
    second = shim.stress_report()
    third = shim.stress_report()
    assert first == second == third
    assert calls["n"] == 1, "o motor real so deveria ser chamado uma vez"


def test_default_construction_shares_one_stress_test_shim_between_quality_observatory_and_council():
    """Prova de fiacao: sem isto, certification_report() pagaria o teste
    de carga real (Missao 59) duas vezes - ver docstring do modulo."""
    svc = _service()
    assert isinstance(svc.quality_observatory.stress_test, _SingleFlightStressTest)
    assert isinstance(svc.council.stress_test, _SingleFlightStressTest)
    assert svc.quality_observatory.stress_test is svc.council.stress_test


def test_explicit_quality_observatory_and_council_are_never_overridden_by_the_shim():
    """Quando o chamador (testes, DI) fornece suas proprias instancias,
    este servico nao deve substituir nada dentro delas."""
    fake_quality = _FakeQualityObservatory()
    fake_council = _FakeCouncil()
    svc = _service(quality_observatory=fake_quality, council=fake_council)
    assert svc.quality_observatory is fake_quality
    assert svc.council is fake_council


# --- dimensoes isoladas -------------------------------------------------------


def test_arquitetura_dimension_healthy_when_classification_is_healthy():
    fake = _FakeArchitectureScoring(classification="healthy", overall_score=91.0)
    dim = _service(architecture_scoring=fake).arquitetura_dimension()
    assert dim["healthy"] is True
    assert dim["blocking"] is True
    assert dim["value"] == 91.0
    assert fake.calls == 1


def test_arquitetura_dimension_concern_when_classification_is_not_healthy():
    fake = _FakeArchitectureScoring(classification="attention")
    dim = _service(architecture_scoring=fake).arquitetura_dimension()
    assert dim["healthy"] is False


def test_governanca_dimension_mirrors_unified_certified():
    dim_ok = _service(evolution_dashboard=_FakeEvolutionDashboard(unified_certified=True)).governanca_dimension()
    assert dim_ok["healthy"] is True

    dim_bad = _service(evolution_dashboard=_FakeEvolutionDashboard(unified_certified=False)).governanca_dimension()
    assert dim_bad["healthy"] is False


def test_seguranca_dimension_strict_policy_passes_only_when_fully_clean():
    fake = _FakeDependencyAudit(missing_count=0, version_mismatch_count=0, unpinned_count=0)
    dim = _service(dependency_audit=fake).seguranca_dimension()
    assert dim["healthy"] is True
    assert fake.calls == 1


def test_seguranca_dimension_strict_policy_blocks_on_unpinned_alone():
    """Diferenca deliberada das Missoes 124/130 (politica leniente, que
    ignora unpinned_count): aqui unpinned sozinho JA bloqueia - ver
    docstring do modulo."""
    fake = _FakeDependencyAudit(missing_count=0, version_mismatch_count=0, unpinned_count=19)
    dim = _service(dependency_audit=fake).seguranca_dimension()
    assert dim["healthy"] is False
    assert dim["value"] == 19


def test_seguranca_dimension_strict_policy_blocks_on_missing_or_mismatch():
    assert _service(dependency_audit=_FakeDependencyAudit(missing_count=1)).seguranca_dimension()["healthy"] is False
    assert _service(dependency_audit=_FakeDependencyAudit(version_mismatch_count=1)).seguranca_dimension()["healthy"] is False


def test_performance_dimension_mirrors_quality_report_performance_subdimension():
    fake = _FakeQualityObservatory(perf_healthy=True, perf_value=True)
    dim = _service(quality_observatory=fake).performance_dimension()
    assert dim["healthy"] is True
    assert fake.calls == 1

    dim_bad = _service(quality_observatory=_FakeQualityObservatory(perf_healthy=False, perf_value=False)).performance_dimension()
    assert dim_bad["healthy"] is False


def test_observabilidade_dimension_healthy_only_when_no_unhealthy_dimensions():
    dim_ok = _service(quality_observatory=_FakeQualityObservatory(unhealthy_dimensions=[])).observabilidade_dimension()
    assert dim_ok["healthy"] is True
    assert dim_ok["value"] == 0

    dim_bad = _service(quality_observatory=_FakeQualityObservatory(unhealthy_dimensions=["bugs", "coverage"])).observabilidade_dimension()
    assert dim_bad["healthy"] is False
    assert dim_bad["value"] == 2


def test_performance_and_observabilidade_share_one_quality_report_call_in_all_dimensions():
    """all_dimensions() chama quality_report() uma unica vez e reusa o
    resultado para as duas dimensoes - nunca duas chamadas."""
    fake = _FakeQualityObservatory()
    svc = _service(quality_observatory=fake)
    dims = svc.all_dimensions()
    assert "performance" in dims and "observabilidade" in dims
    assert fake.calls == 1


def test_recuperacao_dimension_mirrors_recovery_report_healthy_flag():
    fake = _FakeRecovery(healthy=False, warnings=["a", "b"], recoverable_now=5, requires_external_action=10)
    dim = _service(recovery_service=fake).recuperacao_dimension()
    assert dim["healthy"] is False
    assert dim["value"] == 2
    assert fake.calls == 1


def test_qualidade_dimension_mirrors_code_review_clean_flag():
    dim_ok = _service(evolution_dashboard=_FakeEvolutionDashboard(code_review_clean=True)).qualidade_dimension()
    assert dim_ok["healthy"] is True

    dim_bad = _service(evolution_dashboard=_FakeEvolutionDashboard(code_review_clean=False, blocking_findings=3)).qualidade_dimension()
    assert dim_bad["healthy"] is False
    assert dim_bad["value"] == 3


def test_documentacao_dimension_blocks_on_failed_route_or_settings_issue():
    assert _service(documentation=_FakeDocumentation(failed=0)).documentacao_dimension()["healthy"] is True
    assert _service(documentation=_FakeDocumentation(failed=1)).documentacao_dimension()["healthy"] is False
    assert _service(documentation=_FakeDocumentation(settings_issues=["SECRET_KEY ausente"])).documentacao_dimension()["healthy"] is False


def test_operacao_dimension_mirrors_queue_health_report():
    fake = _FakeQueue(healthy=False, warnings=["fila travada"])
    dim = _service(queue_service=fake).operacao_dimension()
    assert dim["healthy"] is False
    assert fake.calls == 1


def test_evolucao_dimension_counts_gaps_across_the_three_buckets():
    dim_ok = _service(evolution_timeline=_FakeEvolutionTimeline(gaps=0)).evolucao_dimension()
    assert dim_ok["healthy"] is True
    assert dim_ok["value"] == 0

    dim_bad = _service(evolution_timeline=_FakeEvolutionTimeline(gaps=3)).evolucao_dimension()
    assert dim_bad["healthy"] is False
    assert dim_bad["value"] == 3


def test_conhecimento_institucional_dimension_is_always_informative_healthy_none():
    """Mesma semantica de sustentabilidade_tecnica_dimension(): nao existe
    no codigo uma meta real de "missoes minimas" - healthy e sempre None,
    independente do valor. `value`/`detail` continuam reais."""
    dim_zero = _service(memory_core=_FakeMemoryCore(mission_count=0)).conhecimento_institucional_dimension()
    assert dim_zero["blocking"] is False
    assert dim_zero["healthy"] is None
    assert dim_zero["value"] == 0

    dim_many = _service(memory_core=_FakeMemoryCore(mission_count=39)).conhecimento_institucional_dimension()
    assert dim_many["healthy"] is None
    assert dim_many["value"] == 39


def test_sustentabilidade_tecnica_dimension_is_always_informative_healthy_none():
    dim = _service(tech_debt_manager=_FakeTechDebtManager(total_items=663)).sustentabilidade_tecnica_dimension()
    assert dim["blocking"] is False
    assert dim["healthy"] is None
    assert dim["value"] == 663


# --- criterios de aprovacao (5, fronteiras reais) -----------------------------


def test_certified_when_everything_healthy_and_council_favoravel():
    fakes = _all_healthy_fakes()
    report = _service(**fakes).certification_report()
    assert report["certified"] is True
    assert report["criteria"]["zero_bloqueadores_criticos"] is True
    assert report["criteria"]["indicadores_dentro_das_metas"] is True
    assert report["criteria"]["evidencias_completas"] is True
    assert report["criteria"]["aprovacao_conselho_tecnico"] is True
    assert report["criteria"]["pronta_para_evolucao_continua"] is True
    assert report["blocking_failures"] == []
    for fake in fakes.values():
        assert fake.calls == 1, "cada dimensao/conselho deve ser calculado exatamente uma vez"


def test_one_blocking_dimension_unhealthy_fails_certification():
    fakes = _all_healthy_fakes()
    fakes["dependency_audit"] = _FakeDependencyAudit(missing_count=1)
    report = _service(**fakes).certification_report()
    assert report["criteria"]["zero_bloqueadores_criticos"] is False
    assert "seguranca" in report["blocking_failures"]
    assert report["certified"] is False


def test_informative_dimensions_never_block_even_when_unhealthy():
    fakes = _all_healthy_fakes()
    fakes["memory_core"] = _FakeMemoryCore(mission_count=0)  # informativo, healthy sempre None
    report = _service(**fakes).certification_report()
    assert "conhecimento_institucional" not in report["blocking_failures"]
    assert "conhecimento_institucional" not in report["target_misses"]
    assert report["criteria"]["zero_bloqueadores_criticos"] is True
    assert report["criteria"]["indicadores_dentro_das_metas"] is True
    assert report["certified"] is True


def test_council_desfavoravel_blocks_certification_even_if_all_dimensions_healthy():
    """Prova explicita do consumo real do parecer da Missao 130: e o
    UNICO criterio nao derivado das 12 dimensoes."""
    fakes = _all_healthy_fakes()
    fakes["council"] = _FakeCouncil(recommendation="desfavoravel", concern_domains=["arquitetura", "operacao", "qa"])
    report = _service(**fakes).certification_report()
    assert report["criteria"]["aprovacao_conselho_tecnico"] is False
    assert report["criteria"]["zero_bloqueadores_criticos"] is True  # as 12 dimensoes continuam saudaveis
    assert report["certified"] is False


def test_council_favoravel_com_restricoes_does_not_block_certification():
    """Heuristica explicita (regra 7): so 'desfavoravel' bloqueia - ver
    docstring do modulo."""
    fakes = _all_healthy_fakes()
    fakes["council"] = _FakeCouncil(recommendation="favoravel_com_restricoes", concern_domains=["arquitetura"])
    report = _service(**fakes).certification_report()
    assert report["criteria"]["aprovacao_conselho_tecnico"] is True
    assert report["certified"] is True


def test_indicadores_dentro_das_metas_has_a_wider_scan_scope_than_zero_bloqueadores_criticos():
    """target_misses varre as 12 dimensoes; blocking_failures so as 10
    bloqueantes - escopos diferentes (ver docstring do modulo). Hoje os
    dois criterios coincidem na pratica porque nenhuma dimensao
    informativa tem healthy=False (sempre None) - este teste prova
    exatamente essa invariante, nao um caso em que eles divergem."""
    fakes = _all_healthy_fakes()
    fakes["tech_debt_manager"] = _FakeTechDebtManager()  # sustentabilidade_tecnica: sempre healthy=None
    fakes["memory_core"] = _FakeMemoryCore(mission_count=0)  # conhecimento_institucional: sempre healthy=None
    report = _service(**fakes).certification_report()
    assert "conhecimento_institucional" not in report["target_misses"]
    assert "sustentabilidade_tecnica" not in report["target_misses"]
    assert "conhecimento_institucional" not in report["blocking_failures"]
    assert report["criteria"]["indicadores_dentro_das_metas"] is True
    assert report["criteria"]["zero_bloqueadores_criticos"] is True
    assert report["certified"] is True


def test_pronta_para_evolucao_continua_is_the_and_of_the_other_four_criteria():
    fakes = _all_healthy_fakes()
    report = _service(**fakes).certification_report()
    criteria = report["criteria"]
    expected = (
        criteria["zero_bloqueadores_criticos"]
        and criteria["indicadores_dentro_das_metas"]
        and criteria["evidencias_completas"]
        and criteria["aprovacao_conselho_tecnico"]
    )
    assert criteria["pronta_para_evolucao_continua"] == expected
    assert report["certified"] == criteria["pronta_para_evolucao_continua"]


def test_evidencias_completas_is_true_for_well_formed_fakes():
    report = _service(**_all_healthy_fakes()).certification_report()
    assert report["criteria"]["evidencias_completas"] is True


# --- render_markdown -----------------------------------------------------------


def test_render_markdown_shows_certificada_when_clean():
    svc = _service(**_all_healthy_fakes())
    text = svc.render_markdown(svc.certification_report())
    assert "CERTIFICADA" in text
    assert "NAO CERTIFICADA" not in text


def test_render_markdown_shows_nao_certificada_and_lists_failures():
    fakes = _all_healthy_fakes()
    fakes["queue_service"] = _FakeQueue(healthy=False, warnings=["fila parada"])
    svc = _service(**fakes)
    text = svc.render_markdown(svc.certification_report())
    assert "NAO CERTIFICADA" in text
    assert "operacao" in text


def test_render_markdown_includes_heuristic_disclaimer():
    svc = _service(**_all_healthy_fakes())
    assert "HEURISTICA" in svc.render_markdown(svc.certification_report()).upper()


# --- contra o repositorio real (apenas dimensoes baratas) ---------------------


def test_cheap_dimensions_against_the_real_repository_are_well_typed():
    """Smoke test honesto: as 10 dimensoes baratas (tudo exceto
    performance/observabilidade, que dependem de
    EnterpriseQualityObservatoryService.quality_report() e portanto do
    teste de carga real da Missao 59 - ver nota de custo no docstring
    do modulo) contra os motores reais, sem mocks."""
    svc = _service()
    for name in (
        "arquitetura_dimension",
        "governanca_dimension",
        "seguranca_dimension",
        "recuperacao_dimension",
        "qualidade_dimension",
        "documentacao_dimension",
        "operacao_dimension",
        "evolucao_dimension",
        "conhecimento_institucional_dimension",
        "sustentabilidade_tecnica_dimension",
    ):
        dim = getattr(svc, name)()
        assert dim["healthy"] in (True, False, None)
        assert "value" in dim
        assert "raw" in dim and dim["raw"] is not None


# --- registro via container -----------------------------------------------------


def test_enterprise_excellence_certification_service_is_registered_via_provide():
    assert "EnterpriseExcellenceCertificationService" in registered_providers()


def test_container_provider_is_callable_end_to_end():
    """Mesma prova feita nas Missoes 124/125/126/130: o provider real do
    container (`provide()`) instancia o servico com a sessao de banco
    resolvida, sem lancar excecao."""
    db = SessionLocal()
    service = get_enterprise_excellence_certification_service(db=db)
    assert isinstance(service, EnterpriseExcellenceCertificationService)


# --- endpoints HTTP (via stub, mesma razao da Missao 130) ----------------------


def test_enterprise_excellence_live_endpoint_returns_stubbed_report():
    fake_report = {
        "certified": True,
        "criteria": {
            "zero_bloqueadores_criticos": True,
            "indicadores_dentro_das_metas": True,
            "evidencias_completas": True,
            "aprovacao_conselho_tecnico": True,
            "pronta_para_evolucao_continua": True,
        },
        "blocking_failures": [],
        "target_misses": [],
        "dimensions": {},
        "council_review": {"recommendation": "favoravel"},
    }

    class _StubService:
        def certification_report(self):
            return fake_report

    real_app.dependency_overrides[get_enterprise_excellence_certification_service] = lambda: _StubService()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/enterprise-excellence/live")
        assert response.status_code == 200
        assert response.json()["certified"] is True
    finally:
        del real_app.dependency_overrides[get_enterprise_excellence_certification_service]


def test_enterprise_excellence_markdown_endpoint_returns_text():
    class _StubService:
        def certification_report(self):
            return {"stub": True}

        def render_markdown(self, report):
            return "# Enterprise Excellence Certification (Missao 131)\nNAO CERTIFICADA (stub)"

    real_app.dependency_overrides[get_enterprise_excellence_certification_service] = lambda: _StubService()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/enterprise-excellence/markdown")
        assert response.status_code == 200
        assert "Enterprise Excellence Certification" in response.text
    finally:
        del real_app.dependency_overrides[get_enterprise_excellence_certification_service]


def test_enterprise_excellence_endpoint_is_overridable_via_container_not_hardcoded():
    fake_report = {"certified": False, "marker": "prova-de-override-m131"}

    class _StubService:
        def certification_report(self):
            return fake_report

    real_app.dependency_overrides[get_enterprise_excellence_certification_service] = lambda: _StubService()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/enterprise-excellence/live")
        assert response.json() == fake_report
    finally:
        del real_app.dependency_overrides[get_enterprise_excellence_certification_service]
