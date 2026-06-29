"""Missao 130 - Strategic Evolution Council.

Cobertura:
1. Cada um dos 6 pareceres de dominio isolado, usando fakes com
   contador de chamadas - prova de reuso direto das missoes 49, 47,
   48, 56, 59 e 127, nunca reimplementacao.
2. Politica de seguranca deliberadamente leniente para `unpinned_count`
   (Missao 124), diferente da politica estrita do gate de release
   (Missao 126) - testada explicitamente.
3. `_recommendation()` (heuristica explicita, regra 7 do CLAUDE.md) -
   limiares 0 / 1-2 / 3+ testados diretamente nas fronteiras.
4. `council_review()` agrega corretamente: cada dominio chamado
   exatamente uma vez, `concern_domains`/`supportive_domains`
   corretos, `change_description` repassado como rotulo (nunca
   analisado).
5. `render_markdown()` - com tudo favoravel e com restricoes/
   desfavoravel - incluindo o aviso de heuristica.
6. Teste contra o repositorio real (sem mocks) - smoke test honesto.
7. Registro real via `provide()` no container (esta missao TEM banco -
   ao contrario das Missoes 128/129 - entao usa `provide()`, nao uma
   funcao dedicada; por isso o teste aqui PROVA PRESENCA no registro,
   o oposto do padrao de auxencia das Missoes 128/129).
8. Endpoints HTTP `/live` e `/markdown`, incluindo teste de override de
   DI (prova que a rota nao esta hardcoded).
"""

from __future__ import annotations

from app.core.container import get_strategic_evolution_council_service, registered_providers
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.strategic_evolution_council_service import (
    StrategicEvolutionCouncilService,
    _recommendation,
)
from fastapi.testclient import TestClient


def _service(**kwargs) -> StrategicEvolutionCouncilService:
    db = SessionLocal()
    return StrategicEvolutionCouncilService(db, **kwargs)


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


class _FakeCodeReview:
    def __init__(self, clean: bool = True, total_blocking: int = 0) -> None:
        self._clean = clean
        self._total_blocking = total_blocking
        self.calls = 0

    def review_repository(self) -> dict:
        self.calls += 1
        return {
            "clean": self._clean,
            "total_files_scanned": 10,
            "files_with_findings": 0 if self._clean else 1,
            "total_blocking_findings": self._total_blocking,
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


class _FakeStressTest:
    def __init__(self, clean: bool = True) -> None:
        self._clean = clean
        self.calls = 0

    def stress_report(self) -> dict:
        self.calls += 1
        return {"clean": self._clean}


class _FakeRecovery:
    def __init__(self, healthy: bool = True, warnings: list[str] | None = None) -> None:
        self._healthy = healthy
        self._warnings = warnings or []
        self.calls = 0

    def recovery_report(self) -> dict:
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


def _all_healthy_fakes() -> dict:
    return {
        "architecture_scoring": _FakeArchitectureScoring(),
        "code_review": _FakeCodeReview(),
        "dependency_audit": _FakeDependencyAudit(),
        "stress_test": _FakeStressTest(),
        "recovery_service": _FakeRecovery(),
        "documentation": _FakeDocumentation(),
    }


# --- pareceres de dominio isolados -------------------------------------------


def test_architecture_opinion_healthy_when_classification_is_healthy():
    fake = _FakeArchitectureScoring(classification="healthy", overall_score=91.0)
    svc = _service(architecture_scoring=fake)
    opinion = svc.architecture_opinion()
    assert opinion["healthy"] is True
    assert opinion["value"] == 91.0
    assert fake.calls == 1


def test_architecture_opinion_concern_when_classification_is_not_healthy():
    fake = _FakeArchitectureScoring(classification="attention", attention=["complexidade"])
    svc = _service(architecture_scoring=fake)
    opinion = svc.architecture_opinion()
    assert opinion["healthy"] is False


def test_qa_opinion_mirrors_code_review_clean_flag():
    fake_clean = _FakeCodeReview(clean=True, total_blocking=0)
    assert _service(code_review=fake_clean).qa_opinion()["healthy"] is True

    fake_dirty = _FakeCodeReview(clean=False, total_blocking=3)
    opinion = _service(code_review=fake_dirty).qa_opinion()
    assert opinion["healthy"] is False
    assert opinion["value"] == 3


def test_security_opinion_passes_when_nothing_missing_or_mismatched():
    fake = _FakeDependencyAudit(missing_count=0, version_mismatch_count=0, unpinned_count=0)
    svc = _service(dependency_audit=fake)
    opinion = svc.security_opinion()
    assert opinion["healthy"] is True
    assert fake.calls == 1


def test_security_opinion_ignores_unpinned_count_by_design():
    """Politica leniente (Missao 124), nao a estrita do gate (Missao
    126): mesmo com muitas dependencias sem pin, o parecer continua
    favoravel se nada estiver faltando ou com versao divergente."""
    fake = _FakeDependencyAudit(missing_count=0, version_mismatch_count=0, unpinned_count=19)
    opinion = _service(dependency_audit=fake).security_opinion()
    assert opinion["healthy"] is True
    assert opinion["raw"]["unpinned_count"] == 19


def test_security_opinion_blocks_on_missing_dependency():
    fake = _FakeDependencyAudit(missing_count=1, version_mismatch_count=0, unpinned_count=0)
    opinion = _service(dependency_audit=fake).security_opinion()
    assert opinion["healthy"] is False


def test_security_opinion_blocks_on_version_mismatch():
    fake = _FakeDependencyAudit(missing_count=0, version_mismatch_count=2, unpinned_count=0)
    opinion = _service(dependency_audit=fake).security_opinion()
    assert opinion["healthy"] is False
    assert opinion["value"] == 2


def test_performance_opinion_mirrors_stress_report_clean_flag():
    fake = _FakeStressTest(clean=True)
    svc = _service(stress_test=fake)
    opinion = svc.performance_opinion()
    assert opinion["healthy"] is True
    assert fake.calls == 1

    opinion_dirty = _service(stress_test=_FakeStressTest(clean=False)).performance_opinion()
    assert opinion_dirty["healthy"] is False


def test_operacao_opinion_mirrors_recovery_report():
    fake = _FakeRecovery(healthy=False, warnings=["fila travada", "5 jobs presos"])
    svc = _service(recovery_service=fake)
    opinion = svc.operacao_opinion()
    assert opinion["healthy"] is False
    assert opinion["value"] == 2
    assert fake.calls == 1


def test_documentacao_opinion_passes_when_clean():
    fake = _FakeDocumentation(failed=0, settings_issues=[])
    opinion = _service(documentation=fake).documentacao_opinion()
    assert opinion["healthy"] is True


def test_documentacao_opinion_blocks_on_failed_route_alone():
    fake = _FakeDocumentation(failed=1, settings_issues=[])
    opinion = _service(documentation=fake).documentacao_opinion()
    assert opinion["healthy"] is False
    assert opinion["value"] == 1


def test_documentacao_opinion_blocks_on_settings_issue_alone():
    fake = _FakeDocumentation(failed=0, settings_issues=["SECRET_KEY ausente"])
    opinion = _service(documentation=fake).documentacao_opinion()
    assert opinion["healthy"] is False
    assert opinion["value"] == 1


# --- heuristica de recomendacao (regra 7) ------------------------------------


def test_recommendation_heuristic_thresholds():
    assert _recommendation(0) == "favoravel"
    assert _recommendation(1) == "favoravel_com_restricoes"
    assert _recommendation(2) == "favoravel_com_restricoes"
    assert _recommendation(3) == "desfavoravel"
    assert _recommendation(6) == "desfavoravel"


# --- agregacao: council_review() ---------------------------------------------


def test_council_review_is_favoravel_when_all_six_domains_healthy():
    fakes = _all_healthy_fakes()
    svc = _service(**fakes)
    report = svc.council_review()
    assert report["recommendation"] == "favoravel"
    assert report["concern_domains"] == []
    assert report["supportive_domains"] == [
        "arquitetura",
        "documentacao",
        "operacao",
        "performance",
        "qa",
        "seguranca",
    ]
    for fake in fakes.values():
        assert fake.calls == 1, "cada dominio deve ser calculado exatamente uma vez"


def test_council_review_is_favoravel_com_restricoes_with_one_concern():
    fakes = _all_healthy_fakes()
    fakes["stress_test"] = _FakeStressTest(clean=False)
    report = _service(**fakes).council_review()
    assert report["recommendation"] == "favoravel_com_restricoes"
    assert report["concern_domains"] == ["performance"]


def test_council_review_is_favoravel_com_restricoes_with_two_concerns():
    fakes = _all_healthy_fakes()
    fakes["stress_test"] = _FakeStressTest(clean=False)
    fakes["code_review"] = _FakeCodeReview(clean=False, total_blocking=1)
    report = _service(**fakes).council_review()
    assert report["recommendation"] == "favoravel_com_restricoes"
    assert report["concern_domains"] == ["performance", "qa"]


def test_council_review_is_desfavoravel_with_three_or_more_concerns():
    fakes = _all_healthy_fakes()
    fakes["stress_test"] = _FakeStressTest(clean=False)
    fakes["code_review"] = _FakeCodeReview(clean=False, total_blocking=1)
    fakes["recovery_service"] = _FakeRecovery(healthy=False, warnings=["x"])
    report = _service(**fakes).council_review()
    assert report["recommendation"] == "desfavoravel"
    assert report["concern_domains"] == ["operacao", "performance", "qa"]


def test_council_review_change_description_is_passed_through_as_label_only():
    fakes = _all_healthy_fakes()
    report = _service(**fakes).council_review(change_description="migrar fila para Redis")
    assert report["change_description"] == "migrar fila para Redis"
    # nada na agregacao depende do texto - mesmo veredito de quando None
    fakes2 = _all_healthy_fakes()
    report2 = _service(**fakes2).council_review()
    assert report["recommendation"] == report2["recommendation"]


def test_council_review_change_description_defaults_to_none():
    report = _service(**_all_healthy_fakes()).council_review()
    assert report["change_description"] is None


# --- render_markdown ----------------------------------------------------------


def test_render_markdown_shows_favoravel_label_when_clean():
    report = _service(**_all_healthy_fakes()).council_review()
    text = _service(**_all_healthy_fakes()).render_markdown(report)
    assert "FAVORAVEL" in text
    assert "Dominios com preocupacao" not in text


def test_render_markdown_lists_concern_domains_when_present():
    fakes = _all_healthy_fakes()
    fakes["documentation"] = _FakeDocumentation(failed=2, settings_issues=[])
    svc = _service(**fakes)
    report = svc.council_review()
    text = svc.render_markdown(report)
    assert "FAVORAVEL COM RESTRICOES" in text
    assert "documentacao" in text
    assert "Dominios com preocupacao" in text


def test_render_markdown_includes_heuristic_disclaimer():
    text = _service(**_all_healthy_fakes()).render_markdown()
    assert "HEURISTICA" in text


# --- contra o repositorio real -------------------------------------------------


def test_council_review_against_real_repository_has_well_typed_fields():
    svc = _service()
    report = svc.council_review()
    assert report["recommendation"] in ("favoravel", "favoravel_com_restricoes", "desfavoravel")
    assert isinstance(report["concern_domains"], list)
    assert isinstance(report["supportive_domains"], list)
    for name in ("arquitetura", "qa", "seguranca", "performance", "operacao", "documentacao"):
        assert name in report["opinions"]
        assert isinstance(report["opinions"][name]["healthy"], bool)
    # render_markdown nao deve levantar excecao contra o relatorio real
    assert isinstance(svc.render_markdown(report), str)


# --- registro via container ----------------------------------------------------


def test_strategic_evolution_council_service_is_registered_via_provide():
    assert "StrategicEvolutionCouncilService" in registered_providers()


# --- endpoints HTTP --------------------------------------------------------------


def test_evolution_council_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/evolution-council/live")
    assert response.status_code == 200
    body = response.json()
    assert "recommendation" in body
    assert "opinions" in body


def test_evolution_council_live_endpoint_passes_change_description_to_service():
    """Prova que a rota repassa o query param ao servico - via stub (nao
    o motor real), pelo mesmo motivo documentado na Missao 124: evitar
    disparar `ArchitectureStressTestService.stress_report()` real (custo
    de dezenas de segundos, ja coberto pelos testes `_endpoint_returns_
    real_computed_report` e `_markdown_endpoint_returns_text` abaixo) so
    para provar passagem de parametro, que e uma questao de fiacao, nao
    de calculo."""

    captured: dict[str, str | None] = {}

    class _StubService:
        def council_review(self, change_description=None):
            captured["value"] = change_description
            return {"change_description": change_description}

    real_app.dependency_overrides[get_strategic_evolution_council_service] = lambda: _StubService()
    try:
        with TestClient(real_app) as client:
            response = client.get(
                "/api/v1/evolution-council/live",
                params={"change_description": "adicionar cache distribuido"},
            )
        assert response.status_code == 200
        assert response.json()["change_description"] == "adicionar cache distribuido"
        assert captured["value"] == "adicionar cache distribuido"
    finally:
        del real_app.dependency_overrides[get_strategic_evolution_council_service]


def test_evolution_council_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/evolution-council/markdown")
    assert response.status_code == 200
    assert "Conselho Estrategico de Evolucao" in response.text


def test_evolution_council_endpoint_is_overridable_via_container_not_hardcoded():
    fake_report = {
        "generated_at": "2026-06-28T00:00:00Z",
        "change_description": None,
        "recommendation": "favoravel",
        "concern_domains": [],
        "supportive_domains": ["arquitetura"],
        "opinions": {},
    }

    class _StubService:
        def council_review(self, change_description=None):
            return fake_report

    def _override():
        return _StubService()

    real_app.dependency_overrides[get_strategic_evolution_council_service] = _override
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/evolution-council/live")
        assert response.json() == fake_report
    finally:
        del real_app.dependency_overrides[get_strategic_evolution_council_service]
