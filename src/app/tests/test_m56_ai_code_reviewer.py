"""Missao 56 - AI Code Reviewer. Suite dedicada."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.container import get_code_review_service, registered_providers
from app.main import app as real_app
from app.services.code_review_service import CodeReviewService


def _service() -> CodeReviewService:
    return CodeReviewService()


# --- Estado real do repositorio -------------------------------------------------

def test_review_repository_is_clean_against_the_real_repository():
    report = _service().review_repository()
    assert report["clean"] is True
    assert report["total_blocking_findings"] == 0
    assert report["total_files_scanned"] > 200


def test_review_repository_excludes_tests_directory():
    report = _service().review_repository()
    for file_report in report["per_file"]:
        assert not file_report["file"].startswith("tests/")
        assert "/tests/" not in file_report["file"]


def test_review_repository_rule_counts_are_internally_consistent():
    report = _service().review_repository()
    total_findings_per_file = sum(len(f["findings"]) for f in report["per_file"])
    assert sum(report["rule_counts"].values()) == total_findings_per_file


# --- Regras bloqueantes: deteccao real ------------------------------------------

def test_bare_except_is_flagged_as_blocking():
    source = (
        "def risky():\n"
        "    try:\n"
        "        pass\n"
        "    except:\n"
        "        pass\n"
    )
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "bare_except" in rules
    assert result["blocking_count"] == 1


def test_typed_except_is_not_flagged_as_bare_except():
    source = (
        "def safe():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError:\n"
        "        pass\n"
    )
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "bare_except" not in rules
    assert result["blocking_count"] == 0


def test_mutable_default_argument_list_is_flagged():
    source = "def f(items=[]):\n    return items\n"
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "mutable_default_argument" in rules
    assert result["blocking_count"] == 1


def test_mutable_default_argument_dict_is_flagged():
    source = "def f(opts={}):\n    return opts\n"
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "mutable_default_argument" in rules


def test_immutable_default_argument_is_not_flagged():
    source = "def f(count=0, name='x', items=None):\n    return count, name, items\n"
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "mutable_default_argument" not in rules


def test_wildcard_import_is_flagged():
    source = "from os import *\n\n\ndef f():\n    return 1\n"
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "wildcard_import" in rules
    assert result["blocking_count"] == 1


def test_explicit_import_is_not_flagged_as_wildcard():
    source = "from os import path\n\n\ndef f():\n    return path\n"
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "wildcard_import" not in rules


def test_syntax_error_file_is_reported_as_blocking_not_silently_skipped():
    source = "def f(:\n    pass\n"
    result = _service().review_file(source=source, label="broken.py")
    assert result["blocking_count"] == 1
    assert result["findings"][0]["rule"] == "syntax_error"


# --- Regras informativas: nunca bloqueiam ---------------------------------------

def test_missing_docstring_is_informative_not_blocking():
    source = "def public_function():\n    return 1\n"
    result = _service().review_file(source=source, label="synthetic.py")
    findings = [f for f in result["findings"] if f["rule"] == "missing_docstring"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "informative"
    assert result["blocking_count"] == 0


def test_function_with_docstring_is_not_flagged_for_missing_docstring():
    source = 'def public_function():\n    """Tem docstring."""\n    return 1\n'
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "missing_docstring" not in rules


def test_private_function_without_docstring_is_not_flagged():
    source = "def _helper():\n    return 1\n"
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "missing_docstring" not in rules


def test_long_function_is_flagged_when_over_threshold():
    body_lines = "\n".join(f"    x{i} = {i}" for i in range(70))
    source = f"def _long():\n{body_lines}\n    return x0\n"
    result = _service().review_file(source=source, label="synthetic.py")
    findings = [f for f in result["findings"] if f["rule"] == "long_function"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "informative"
    assert result["blocking_count"] == 0


def test_short_function_is_not_flagged_for_length():
    source = "def _short():\n    return 1\n"
    result = _service().review_file(source=source, label="synthetic.py")
    rules = {f["rule"] for f in result["findings"]}
    assert "long_function" not in rules


def test_todo_marker_is_detected_and_informative():
    source = "def _f():\n    # TODO: revisar isso depois\n    return 1\n"
    result = _service().review_file(source=source, label="synthetic.py")
    findings = [f for f in result["findings"] if f["rule"] == "todo_marker"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "informative"
    assert result["blocking_count"] == 0


def test_informative_only_file_keeps_repository_clean():
    """Um arquivo so com achados informativos nao deve, por si so, derrubar
    `clean` no agregado de repositorio - mesma filosofia "informativo, nao
    bloqueante" da Missao 55 (`di_adoption`)."""
    source = "def public_function():\n    return 1\n"
    result = _service().review_file(source=source, label="synthetic.py")
    assert result["blocking_count"] == 0
    assert any(f["severity"] == "informative" for f in result["findings"])


# --- render_markdown -------------------------------------------------------------

def test_render_markdown_reports_clean_verdict_for_the_real_repository():
    markdown = _service().render_markdown()
    assert "REVISAO LIMPA" in markdown
    assert "Arquivos varridos" in markdown


def test_render_markdown_lists_blocking_findings_when_present():
    fake_report = {
        "clean": False,
        "total_files_scanned": 1,
        "files_with_findings": 1,
        "total_blocking_findings": 1,
        "rule_counts": {"bare_except": 1},
        "per_file": [
            {
                "file": "app/fake_module.py",
                "blocking_count": 1,
                "findings": [
                    {
                        "rule": "bare_except",
                        "severity": "blocking",
                        "line": 10,
                        "detail": "except: sem tipo",
                    }
                ],
            }
        ],
    }
    markdown = _service().render_markdown(fake_report)
    assert "ACHADO BLOQUEANTE DETECTADO" in markdown
    assert "app/fake_module.py" in markdown
    assert "bare_except" in markdown


# --- Container (Missao 52) e endpoints HTTP -------------------------------------

def test_code_review_service_itself_is_not_in_the_provider_registry():
    """Mesma decisao documentada na Missao 55: services sem `db` nao usam
    `provide()`, por isso nao aparecem em `registered_providers()`."""
    assert "CodeReviewService" not in registered_providers()


def test_code_review_live_endpoint_returns_real_computed_report():
    client = TestClient(real_app)
    response = client.get("/api/v1/code-review/live")
    assert response.status_code == 200
    payload = response.json()
    assert "clean" in payload
    assert "total_files_scanned" in payload


def test_code_review_markdown_endpoint_returns_text():
    client = TestClient(real_app)
    response = client.get("/api/v1/code-review/markdown")
    assert response.status_code == 200
    assert "Revisao Automatica de Codigo" in response.text


def test_code_review_endpoint_is_overridable_via_container_not_hardcoded():
    class _FakeReviewService:
        def review_repository(self):
            return {
                "clean": False,
                "total_files_scanned": 1,
                "files_with_findings": 1,
                "total_blocking_findings": 1,
                "rule_counts": {"bare_except": 1},
                "per_file": [],
            }

    real_app.dependency_overrides[get_code_review_service] = lambda: _FakeReviewService()
    try:
        client = TestClient(real_app)
        response = client.get("/api/v1/code-review/live")
        assert response.status_code == 200
        assert response.json()["clean"] is False
        assert response.json()["total_blocking_findings"] == 1
    finally:
        real_app.dependency_overrides.pop(get_code_review_service, None)
