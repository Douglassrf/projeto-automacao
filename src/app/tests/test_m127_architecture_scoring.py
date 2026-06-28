"""Missao 127 - Continuous Architecture Scoring.

Cobertura:
1. Cada um dos 5 eixos isolado, com fakes com contador de chamadas -
   prova de reuso direto (M55/M56/M58), nunca reimplementacao.
2. Limiar heuristico de classificacao (`_HEALTHY_SCORE_THRESHOLD = 70`)
   nas duas bordas exatas.
3. `cohesion_score()` contra uma pasta sintetica (arquivo com 0, 1 e 2+
   classes de topo) - prova do calculo real via AST.
4. `score_report()` agrega os 5 eixos corretamente (media simples,
   `attention_dimensions` lista exatamente os eixos abaixo do limiar).
5. `render_markdown()` - com tudo saudavel e com eixos em atencao.
6. Smoke test contra o repositorio real (sem mocks, sem TestClient).
7. Registro via `provide()` no container.
8. Endpoints HTTP `/live` e `/markdown`, incluindo teste de override de DI.
"""

from __future__ import annotations

from pathlib import Path

from app.core.container import get_architecture_scoring_service, registered_providers
from app.main import app as real_app
from app.services.architecture_scoring_service import ContinuousArchitectureScoringService
from fastapi.testclient import TestClient


def _service(**kwargs) -> ContinuousArchitectureScoringService:
    return ContinuousArchitectureScoringService(**kwargs)


class _FakeArchitectureAudit:
    def __init__(
        self,
        config_clean: bool = True,
        routing_clean: bool = True,
        collisions_clean: bool = True,
        adoption_rate: float = 1.0,
        via_container: int = 5,
        total_modules: int = 5,
    ) -> None:
        self._config_clean = config_clean
        self._routing_clean = routing_clean
        self._collisions_clean = collisions_clean
        self._adoption_rate = adoption_rate
        self._via_container = via_container
        self._total_modules = total_modules
        self.audit_calls = 0
        self.di_adoption_calls = 0

    def audit(self) -> dict:
        self.audit_calls += 1
        return {
            "clean": self._config_clean and self._routing_clean and self._collisions_clean,
            "config_centralization": {"clean": self._config_clean},
            "route_discovery": {"clean": self._routing_clean},
            "route_collisions": {"clean": self._collisions_clean},
        }

    def audit_di_adoption(self) -> dict:
        self.di_adoption_calls += 1
        return {
            "adoption_rate": self._adoption_rate,
            "via_container": ["m"] * self._via_container,
            "total_route_modules": self._total_modules,
        }


class _FakeCodeReview:
    def __init__(self, total_files_scanned: int = 10, long_function_count: int = 0) -> None:
        self._total_files_scanned = total_files_scanned
        self._long_function_count = long_function_count
        self.calls = 0

    def review_repository(self) -> dict:
        self.calls += 1
        return {
            "total_files_scanned": self._total_files_scanned,
            "rule_counts": {"long_function": self._long_function_count} if self._long_function_count else {},
        }


class _FakeTechDebtManager:
    def __init__(self, files_with_debt: int = 0) -> None:
        self._files_with_debt = files_with_debt
        self.calls = 0

    def debt_report(self) -> dict:
        self.calls += 1
        return {"summary": {"files_with_debt": self._files_with_debt}}


def _write_service_file(directory: Path, name: str, class_count: int) -> None:
    body_lines = []
    for i in range(class_count):
        body_lines.append(f"class C{i}:\n    pass\n")
    if class_count == 0:
        body_lines.append("def helper():\n    pass\n")
    (directory / name).write_text("\n".join(body_lines), encoding="utf-8")


# --- modularidade -------------------------------------------------------


def test_modularity_score_is_100_when_all_three_axes_clean():
    fake = _FakeArchitectureAudit(config_clean=True, routing_clean=True, collisions_clean=True)
    svc = _service(architecture_audit=fake)
    result = svc.modularity_score()
    assert result["score"] == 100.0
    assert result["classification"] == "healthy"
    assert fake.audit_calls == 1


def test_modularity_score_drops_when_one_axis_dirty():
    fake = _FakeArchitectureAudit(config_clean=True, routing_clean=False, collisions_clean=True)
    svc = _service(architecture_audit=fake)
    result = svc.modularity_score()
    assert result["score"] == round(2 / 3 * 100, 2)


# --- acoplamento ----------------------------------------------------------


def test_coupling_score_uses_adoption_rate_directly():
    fake = _FakeArchitectureAudit(adoption_rate=0.8)
    svc = _service(architecture_audit=fake)
    result = svc.coupling_score()
    assert result["score"] == 80.0
    assert fake.di_adoption_calls == 1


def test_coupling_score_zero_adoption_is_attention():
    fake = _FakeArchitectureAudit(adoption_rate=0.0)
    svc = _service(architecture_audit=fake)
    result = svc.coupling_score()
    assert result["score"] == 0.0
    assert result["classification"] == "attention"


# --- coesao (heuristica, contra pasta sintetica) --------------------------


def test_cohesion_score_full_marks_when_every_file_has_one_class(tmp_path):
    _write_service_file(tmp_path, "a_service.py", class_count=1)
    _write_service_file(tmp_path, "b_service.py", class_count=1)
    svc = _service()
    result = svc.cohesion_score(services_dir=tmp_path)
    assert result["score"] == 100.0
    assert result["files_off_convention"] == []


def test_cohesion_score_flags_files_with_zero_or_multiple_classes(tmp_path):
    _write_service_file(tmp_path, "good_service.py", class_count=1)
    _write_service_file(tmp_path, "empty_service.py", class_count=0)
    _write_service_file(tmp_path, "multi_service.py", class_count=2)
    svc = _service()
    result = svc.cohesion_score(services_dir=tmp_path)
    assert result["score"] == round(1 / 3 * 100, 2)
    assert result["files_off_convention"] == ["empty_service.py", "multi_service.py"]


def test_cohesion_score_ignores_init_file(tmp_path):
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    _write_service_file(tmp_path, "only_service.py", class_count=1)
    svc = _service()
    result = svc.cohesion_score(services_dir=tmp_path)
    assert result["score"] == 100.0
    assert "__init__.py" not in result["raw"]


# --- complexidade -----------------------------------------------------------


def test_complexity_score_is_100_with_no_long_functions():
    fake = _FakeCodeReview(total_files_scanned=20, long_function_count=0)
    svc = _service(code_review=fake)
    result = svc.complexity_score()
    assert result["score"] == 100.0


def test_complexity_score_drops_with_long_functions():
    fake = _FakeCodeReview(total_files_scanned=10, long_function_count=3)
    svc = _service(code_review=fake)
    result = svc.complexity_score()
    assert result["score"] == 70.0


def test_complexity_score_clamped_at_zero_when_long_functions_exceed_files():
    fake = _FakeCodeReview(total_files_scanned=2, long_function_count=5)
    svc = _service(code_review=fake)
    result = svc.complexity_score()
    assert result["score"] == 0.0


# --- manutenibilidade -------------------------------------------------------


def test_maintainability_score_is_100_with_no_files_with_debt():
    fake_debt = _FakeTechDebtManager(files_with_debt=0)
    fake_review = _FakeCodeReview(total_files_scanned=15)
    svc = _service(tech_debt_manager=fake_debt, code_review=fake_review)
    result = svc.maintainability_score()
    assert result["score"] == 100.0
    assert fake_debt.calls == 1


def test_maintainability_score_drops_with_files_with_debt():
    fake_debt = _FakeTechDebtManager(files_with_debt=4)
    fake_review = _FakeCodeReview(total_files_scanned=10)
    svc = _service(tech_debt_manager=fake_debt, code_review=fake_review)
    result = svc.maintainability_score()
    assert result["score"] == 60.0


# --- limiar heuristico de classificacao (bordas exatas) ---------------------


def test_classification_boundary_at_exact_threshold_is_healthy():
    fake = _FakeArchitectureAudit(adoption_rate=0.70)
    svc = _service(architecture_audit=fake)
    result = svc.coupling_score()
    assert result["score"] == 70.0
    assert result["classification"] == "healthy"


def test_classification_just_below_threshold_is_attention():
    fake = _FakeArchitectureAudit(adoption_rate=0.69)
    svc = _service(architecture_audit=fake)
    result = svc.coupling_score()
    assert result["score"] == 69.0
    assert result["classification"] == "attention"


# --- agregacao: score_report() ----------------------------------------------


def test_score_report_averages_five_dimensions_with_no_attention_when_all_healthy():
    svc = _service(
        architecture_audit=_FakeArchitectureAudit(adoption_rate=1.0),
        code_review=_FakeCodeReview(total_files_scanned=10, long_function_count=0),
        tech_debt_manager=_FakeTechDebtManager(files_with_debt=0),
    )
    # cohesion_score() le um diretorio real por padrao (sem fake injetavel
    # nas outras 4 dependencias) - aqui isolamos so a aritmetica de
    # agregacao, substituindo por um valor fixo de coesao 100; a
    # corretude do calculo de coesao em si jah tem testes de fronteira
    # dedicados acima, contra pastas sinteticas via `services_dir=`.
    svc.cohesion_score = lambda: {  # type: ignore[method-assign]
        "score": 100.0,
        "classification": "healthy",
        "signal": "ok",
        "detail": "fake para isolar agregacao",
        "files_off_convention": [],
        "raw": {},
    }
    report = svc.score_report()
    assert report["overall_score"] == 100.0
    assert report["overall_classification"] == "healthy"
    assert report["attention_dimensions"] == []
    assert set(report["dimensions"].keys()) == {
        "modularity",
        "coupling",
        "cohesion",
        "complexity",
        "maintainability",
    }


def test_score_report_lists_exact_attention_dimensions():
    svc = _service(
        architecture_audit=_FakeArchitectureAudit(adoption_rate=0.0),
        code_review=_FakeCodeReview(total_files_scanned=10, long_function_count=8),
        tech_debt_manager=_FakeTechDebtManager(files_with_debt=0),
    )
    report = svc.score_report()
    assert "coupling" in report["attention_dimensions"]
    assert "complexity" in report["attention_dimensions"]
    assert "maintainability" not in report["attention_dimensions"]


# --- render_markdown ---------------------------------------------------------


def test_render_markdown_shows_no_attention_section_when_all_healthy():
    svc = _service(
        architecture_audit=_FakeArchitectureAudit(adoption_rate=1.0),
        code_review=_FakeCodeReview(total_files_scanned=10, long_function_count=0),
        tech_debt_manager=_FakeTechDebtManager(files_with_debt=0),
    )
    text = svc.render_markdown()
    assert "ATENCAO" not in text
    assert "100.0/100" in text


def test_render_markdown_lists_attention_dimensions_when_present():
    svc = _service(
        architecture_audit=_FakeArchitectureAudit(adoption_rate=0.0),
        code_review=_FakeCodeReview(total_files_scanned=10, long_function_count=0),
        tech_debt_manager=_FakeTechDebtManager(files_with_debt=0),
    )
    text = svc.render_markdown()
    assert "ATENCAO" in text
    assert "coupling" in text


# --- smoke test contra o repositorio real (sem mocks, sem TestClient) ------


def test_score_report_against_real_repository_has_well_typed_fields():
    svc = _service()
    report = svc.score_report()
    assert isinstance(report["overall_score"], float)
    assert 0.0 <= report["overall_score"] <= 100.0
    for name in ("modularity", "coupling", "cohesion", "complexity", "maintainability"):
        dim = report["dimensions"][name]
        assert isinstance(dim["score"], float)
        assert 0.0 <= dim["score"] <= 100.0
        assert dim["classification"] in ("healthy", "attention")
    assert isinstance(svc.render_markdown(report), str)


# --- registro via container --------------------------------------------------


def test_architecture_scoring_service_is_not_in_the_provider_registry():
    # get_architecture_scoring_service nao usa provide() (mesmo motivo de
    # get_architecture_audit_service/Missao 55, get_code_review_service/
    # Missao 56 e get_tech_debt_manager_service/Missao 58 - nao depende
    # de db) - por isso nao aparece em registered_providers(), de
    # proposito. A prova real de que a rota usa o container (nao um
    # servico hardcoded) e o teste de override de DI, abaixo.
    assert "ContinuousArchitectureScoringService" not in registered_providers()


# --- endpoints HTTP -----------------------------------------------------------


def test_architecture_scoring_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/architecture-scoring/live")
    assert response.status_code == 200
    body = response.json()
    assert "overall_score" in body
    assert "dimensions" in body


def test_architecture_scoring_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/architecture-scoring/markdown")
    assert response.status_code == 200
    assert "Pontuacao Continua de Arquitetura" in response.text


def test_architecture_scoring_endpoint_is_overridable_via_container_not_hardcoded():
    fake_report = {"overall_score": 42.0, "dimensions": {}}

    class _StubService:
        def score_report(self):
            return fake_report

    def _override():
        return _StubService()

    real_app.dependency_overrides[get_architecture_scoring_service] = _override
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/architecture-scoring/live")
        assert response.json() == fake_report
    finally:
        del real_app.dependency_overrides[get_architecture_scoring_service]
