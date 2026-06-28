"""Missao 49 - Auditoria de Dependencias.

Justificativa real coberta por estes testes: `requirements.txt` deste
repositorio declara 19 dependencias e nenhuma delas tem versao fixa
(`==`) - 19/19, 100% sem pin. `DependencyAuditService` le esse arquivo em
tempo real, classifica cada linha como fixada/nao-fixada via
`packaging.requirements.Requirement`, cruza com a versao de fato
instalada via `importlib.metadata` (sem chamadas de rede) e expõe o
resultado via `/dependency-audit/live` e `/dependency-audit/markdown`.

Cobre: parsing de requirements.txt (incluindo linhas com pin, sem pin,
comentario, em branco e nome invalido), cross-reference com o ambiente
instalado (pacote ausente e divergencia de versao via requirements.txt
temporario), o novo campo de configuracao
`dependency_audit_warn_on_unpinned`, a nova regra de
`validate_settings()` e os dois novos endpoints (Missao 49).
"""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.main import app
from app.services.dependency_audit_service import DependencyAuditService, _parse_requirements_text


def test_parse_requirements_text_classifies_pinned_and_unpinned():
    text = "fastapi\npydantic==2.5.0\n"
    entries = _parse_requirements_text(text)
    by_name = {entry["name"]: entry for entry in entries}
    assert by_name["fastapi"]["pinned"] is False
    assert by_name["fastapi"]["pinned_version"] is None
    assert by_name["pydantic"]["pinned"] is True
    assert by_name["pydantic"]["pinned_version"] == "2.5.0"


def test_parse_requirements_text_ignores_blank_lines_and_comments():
    text = "\n# comentario\nfastapi\n\n   \n-r outro.txt\n"
    entries = _parse_requirements_text(text)
    names = [entry["name"] for entry in entries]
    assert names == ["fastapi"]


def test_parse_requirements_text_flags_invalid_lines_with_parse_error():
    text = "isto nao e um requirement valido !!\n"
    entries = _parse_requirements_text(text)
    assert len(entries) == 1
    assert entries[0]["name"] is None
    assert entries[0]["parse_error"] is not None


def test_audit_reads_real_requirements_file_and_finds_zero_pins():
    snapshot = DependencyAuditService().audit()
    assert snapshot["total_declared"] == 19
    assert snapshot["pinned_count"] == 0
    assert snapshot["unpinned_count"] == 19
    assert snapshot["missing_count"] == 0


def test_audit_flags_every_unpinned_dependency_as_issue_by_default():
    settings = get_settings()
    previous = settings.dependency_audit_warn_on_unpinned
    try:
        settings.dependency_audit_warn_on_unpinned = True
        snapshot = DependencyAuditService(settings).audit()
        assert len(snapshot["issues"]) >= snapshot["unpinned_count"]
        assert any("fastapi" in issue and "sem versão fixa" in issue for issue in snapshot["issues"])
    finally:
        settings.dependency_audit_warn_on_unpinned = previous


def test_audit_suppresses_unpinned_issues_when_flag_disabled():
    settings = get_settings()
    previous = settings.dependency_audit_warn_on_unpinned
    try:
        settings.dependency_audit_warn_on_unpinned = False
        snapshot = DependencyAuditService(settings).audit()
        assert not any("sem versão fixa" in issue for issue in snapshot["issues"])
        # a lista bruta de dependencias continua mostrando o estado real
        assert snapshot["unpinned_count"] == 19
    finally:
        settings.dependency_audit_warn_on_unpinned = previous


def test_audit_detects_missing_package_with_custom_requirements_file(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("este-pacote-nao-existe-em-nenhum-lugar\n", encoding="utf-8")
    snapshot = DependencyAuditService(requirements_file=req_file).audit()
    assert snapshot["total_declared"] == 1
    assert snapshot["missing_count"] == 1
    dep = snapshot["dependencies"][0]
    assert dep["missing"] is True
    assert dep["installed_version"] is None
    assert any("não está instalado" in issue for issue in snapshot["issues"])


def test_audit_detects_version_mismatch_with_custom_requirements_file(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("fastapi==0.0.1\n", encoding="utf-8")
    snapshot = DependencyAuditService(requirements_file=req_file).audit()
    dep = snapshot["dependencies"][0]
    assert dep["pinned"] is True
    assert dep["pinned_version"] == "0.0.1"
    assert dep["missing"] is False
    assert dep["version_mismatch"] is True
    assert snapshot["version_mismatch_count"] == 1
    assert any("requirements.txt fixa 0.0.1" in issue for issue in snapshot["issues"])


def test_audit_handles_missing_requirements_file_gracefully(tmp_path):
    snapshot = DependencyAuditService(requirements_file=tmp_path / "nao_existe.txt").audit()
    assert snapshot["total_declared"] == 0
    assert snapshot["issues"] == []


def test_render_markdown_contains_key_sections():
    md = DependencyAuditService().render_markdown()
    assert "# Auditoria de Dependencias" in md
    assert "## Dependências declaradas" in md
    assert "fastapi" in md


def test_render_markdown_accepts_precomputed_snapshot():
    svc = DependencyAuditService()
    snapshot = svc.audit()
    md = svc.render_markdown(snapshot)
    assert str(snapshot["total_declared"]) in md


def test_config_schema_version_bumped_for_mission_49():
    # Comparação por tupla (não igualdade estrita) - mesma lição aprendida
    # ao corrigir o teste equivalente da Missão 48: uma missão futura (50)
    # vai bumpar a versão de novo, e esta asserção não deve quebrar por isso.
    current = tuple(int(part) for part in CONFIG_SCHEMA_VERSION.split("."))
    assert current >= (1, 8, 0)


def test_validate_settings_rejects_disabled_warn_on_unpinned_in_production():
    settings = get_settings()
    previous = settings.dependency_audit_warn_on_unpinned
    try:
        settings.dependency_audit_warn_on_unpinned = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("dependency_audit_warn_on_unpinned" in issue for issue in issues)
    finally:
        settings.dependency_audit_warn_on_unpinned = previous


def test_validate_settings_accepts_default_warn_on_unpinned_in_production():
    settings = get_settings()
    previous = settings.dependency_audit_warn_on_unpinned
    try:
        settings.dependency_audit_warn_on_unpinned = True
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert not any("dependency_audit_warn_on_unpinned" in issue for issue in issues)
    finally:
        settings.dependency_audit_warn_on_unpinned = previous


def test_validate_settings_ignores_warn_on_unpinned_flag_outside_production():
    settings = get_settings()
    previous = settings.dependency_audit_warn_on_unpinned
    try:
        settings.dependency_audit_warn_on_unpinned = False
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert not any("dependency_audit_warn_on_unpinned" in issue for issue in issues)
    finally:
        settings.dependency_audit_warn_on_unpinned = previous


def test_live_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.get("/api/v1/dependency-audit/live")
    assert response.status_code == 200
    body = response.json()
    assert body["total_declared"] == 19
    assert "dependencies" in body
    assert isinstance(body["dependencies"], list)
    assert len(body["dependencies"]) == 19


def test_live_endpoint_includes_fastapi_as_unpinned_dependency():
    client = TestClient(app)
    response = client.get("/api/v1/dependency-audit/live")
    body = response.json()
    by_name = {dep["name"]: dep for dep in body["dependencies"]}
    assert by_name["fastapi"]["pinned"] is False


def test_markdown_endpoint_returns_text_markdown():
    client = TestClient(app)
    response = client.get("/api/v1/dependency-audit/markdown")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "# Auditoria de Dependencias" in response.text
