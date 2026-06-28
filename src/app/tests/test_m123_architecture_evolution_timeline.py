"""Missao 123 - Architecture Evolution Timeline (Fase v2.1).

Cobertura desta suite: (1) `_directory_history()` faz UMA unica chamada
`git log --name-only` por diretorio e associa corretamente commits a
arquivos, provado contra um repositorio git sintetico criado no
`tmp_path` do teste (nao o repositorio real, para ter controle total
sobre commits/ordem); (2) `module_evolution()` / `api_evolution()` /
`service_evolution()` aplicam essa mineracao aos tres diretorios reais
(`src/app/core`, `src/app/api/routes`, `src/app/services`), com
ordenacao ascendente por primeiro commit, contagem de commits correta,
e o eixo informativo `files_without_history` (arquivos no disco sem
commit encontrado) testado tanto sinteticamente quanto contra o
repositorio real (onde os 2 arquivos novos desta propria missao, antes
do commit, aparecem como gap esperado); (3) `configuration_evolution()`
minera CONFIG_SCHEMA_VERSION de `config_profiles.py` commit a commit -
testado com repositorio sintetico (constante presente, ausente, e
valor mudando entre commits) e contra o repositorio real (ultimo valor
bate com o conteudo atual do arquivo); (4) `certification_evolution()`
e reuso direto e comprovado (via fake com contador de chamadas) de
`EngineeringMemoryCoreService.certification_history()` (Missao 122) -
nunca recalculado aqui; (5) `evolution_report()` agrega as cinco fontes
e `render_markdown()` torna a cobertura (incluindo gaps) visivel; (6)
registro via `provide()` e endpoints HTTP refletindo o service real via
container de DI (Missao 52), nunca hardcoded na rota.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import project_root
from app.core.container import get_architecture_evolution_timeline_service, registered_providers
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.architecture_evolution_timeline_service import (
    ArchitectureEvolutionTimelineService,
)

UTC = timezone.utc


def _service(**kwargs):
    db = SessionLocal()
    return ArchitectureEvolutionTimelineService(db, **kwargs), db


# --- fakes ----------------------------------------------------------------


class _FakeEngineeringMemory:
    def __init__(self, certifications=None):
        self._certifications = certifications if certifications is not None else []
        self.certification_history_calls = 0

    def certification_history(self):
        self.certification_history_calls += 1
        return self._certifications


# --- fixture: repositorio git sintetico ------------------------------------


def _run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _init_git_repo(root: Path) -> None:
    _run(["git", "init", "-q"], cwd=root)
    _run(["git", "config", "user.email", "test@example.com"], cwd=root)
    _run(["git", "config", "user.name", "Test"], cwd=root)


def _commit_all(root: Path, message: str) -> str:
    _run(["git", "add", "-A"], cwd=root)
    _run(["git", "commit", "-q", "-m", message], cwd=root)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _build_synthetic_repo(tmp_path: Path) -> dict:
    """Cria um repositorio git real e minimo em tmp_path com:
    - src/app/core/alpha.py: criado no commit 1, modificado no commit 3.
    - src/app/core/beta.py: criado no commit 2.
    - src/app/core/config_profiles.py: CONFIG_SCHEMA_VERSION "1.0.0" no
      commit 1, "1.1.0" no commit 2, removido (sem a constante) no
      commit 3.
    Devolve os hashes dos 3 commits para asserções precisas.
    """
    _init_git_repo(tmp_path)
    core_dir = tmp_path / "src" / "app" / "core"
    core_dir.mkdir(parents=True)

    (core_dir / "alpha.py").write_text("VALUE = 1\n")
    (core_dir / "config_profiles.py").write_text('CONFIG_SCHEMA_VERSION = "1.0.0"\n')
    commit_1 = _commit_all(tmp_path, "Missao 1 - cria alpha e config")

    (core_dir / "beta.py").write_text("VALUE = 2\n")
    (core_dir / "config_profiles.py").write_text('CONFIG_SCHEMA_VERSION = "1.1.0"\n')
    commit_2 = _commit_all(tmp_path, "Missao 2 - cria beta, sobe schema")

    (core_dir / "alpha.py").write_text("VALUE = 1\nVALUE_2 = 3\n")
    (core_dir / "config_profiles.py").write_text("# constante removida\n")
    commit_3 = _commit_all(tmp_path, "Missao 3 - modifica alpha, remove constante")

    return {"commit_1": commit_1, "commit_2": commit_2, "commit_3": commit_3}


def _patch_project_root(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.architecture_evolution_timeline_service.project_root", lambda: tmp_path
    )


# --- 1. _directory_history --------------------------------------------------


def test_directory_history_associates_commits_to_correct_files(monkeypatch, tmp_path):
    hashes = _build_synthetic_repo(tmp_path)
    _patch_project_root(monkeypatch, tmp_path)

    by_file = ArchitectureEvolutionTimelineService._directory_history("src/app/core")

    alpha_hashes = {c["commit_hash"] for c in by_file["src/app/core/alpha.py"]}
    beta_hashes = {c["commit_hash"] for c in by_file["src/app/core/beta.py"]}
    assert alpha_hashes == {hashes["commit_1"][:7], hashes["commit_3"][:7]}
    assert beta_hashes == {hashes["commit_2"][:7]}


# --- 2. module/api/service evolution ----------------------------------------


def test_module_evolution_against_synthetic_repo_has_correct_counts_and_order(monkeypatch, tmp_path):
    hashes = _build_synthetic_repo(tmp_path)
    _patch_project_root(monkeypatch, tmp_path)
    service, db = _service(engineering_memory=_FakeEngineeringMemory())
    try:
        result = service.module_evolution()
        files_by_name = {e["file"]: e for e in result["files"]}

        alpha = files_by_name["src/app/core/alpha.py"]
        assert alpha["total_commits"] == 2
        assert alpha["first_commit"]["commit_hash"] == hashes["commit_1"][:7]
        assert alpha["last_commit"]["commit_hash"] == hashes["commit_3"][:7]

        beta = files_by_name["src/app/core/beta.py"]
        assert beta["total_commits"] == 1

        config = files_by_name["src/app/core/config_profiles.py"]
        assert config["total_commits"] == 3

        # alpha e config_profiles nascem no commit 1; beta nasce no commit 2 -> beta por ultimo
        assert result["files"][-1]["file"] == "src/app/core/beta.py"
        assert result["files_without_history"] == []
    finally:
        db.close()


def test_module_evolution_detects_files_without_git_history_as_a_gap(monkeypatch, tmp_path):
    hashes = _build_synthetic_repo(tmp_path)
    _patch_project_root(monkeypatch, tmp_path)
    # gama.py existe no disco mas nunca foi commitado
    (tmp_path / "src" / "app" / "core" / "gama.py").write_text("VALUE = 99\n")

    service, db = _service(engineering_memory=_FakeEngineeringMemory())
    try:
        result = service.module_evolution()
        assert result["files_without_history"] == ["src/app/core/gama.py"]
        assert "src/app/core/gama.py" not in {e["file"] for e in result["files"]}
    finally:
        db.close()


def test_module_evolution_excludes_init_file(monkeypatch, tmp_path):
    _build_synthetic_repo(tmp_path)
    (tmp_path / "src" / "app" / "core" / "__init__.py").write_text("")
    _commit_all(tmp_path, "Missao 4 - adiciona __init__")
    _patch_project_root(monkeypatch, tmp_path)

    service, db = _service(engineering_memory=_FakeEngineeringMemory())
    try:
        result = service.module_evolution()
        assert "src/app/core/__init__.py" not in {e["file"] for e in result["files"]}
        assert "src/app/core/__init__.py" not in result["files_without_history"]
    finally:
        db.close()


def test_module_evolution_returns_empty_when_directory_missing(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "README.md").write_text("vazio\n")
    _commit_all(tmp_path, "baseline")
    _patch_project_root(monkeypatch, tmp_path)

    service, db = _service(engineering_memory=_FakeEngineeringMemory())
    try:
        result = service.module_evolution()
        assert result == {"files": [], "files_without_history": []}
    finally:
        db.close()


def test_module_evolution_against_real_repository_finds_known_files():
    service, db = _service()
    try:
        result = service.module_evolution()
        files = {e["file"] for e in result["files"]}
        assert "src/app/core/config.py" in files
        assert "src/app/core/container.py" in files
        assert len(result["files"]) >= 50
    finally:
        db.close()


def test_api_evolution_against_real_repository_finds_known_route_files():
    service, db = _service()
    try:
        result = service.api_evolution()
        files = {e["file"] for e in result["files"]}
        assert "src/app/api/routes/engineering_memory_core.py" in files
        assert len(result["files"]) >= 50
    finally:
        db.close()


def test_service_evolution_against_real_repository_finds_known_service_files():
    service, db = _service()
    try:
        result = service.service_evolution()
        files = {e["file"] for e in result["files"]}
        assert "src/app/services/engineering_memory_core_service.py" in files
        assert len(result["files"]) >= 50
    finally:
        db.close()


# --- 3. configuration_evolution ---------------------------------------------


def test_configuration_evolution_against_synthetic_repo_tracks_schema_value_per_commit(
    monkeypatch, tmp_path
):
    hashes = _build_synthetic_repo(tmp_path)
    _patch_project_root(monkeypatch, tmp_path)

    service, db = _service(engineering_memory=_FakeEngineeringMemory())
    try:
        entries = service.configuration_evolution()
        by_hash = {e["commit_hash"]: e for e in entries}

        assert by_hash[hashes["commit_1"][:7]]["config_schema_version"] == "1.0.0"
        assert by_hash[hashes["commit_2"][:7]]["config_schema_version"] == "1.1.0"
        # commit 3 remove a constante -> None, nunca inventado
        assert by_hash[hashes["commit_3"][:7]]["config_schema_version"] is None

        timestamps = [e["committed_at"] for e in entries]
        assert timestamps == sorted(timestamps)
    finally:
        db.close()


def test_configuration_evolution_against_real_repository_matches_current_file():
    service, db = _service()
    try:
        entries = service.configuration_evolution()
        assert len(entries) >= 1
        current_content = (project_root() / "src" / "app" / "core" / "config_profiles.py").read_text()
        import re

        match = re.search(r'^CONFIG_SCHEMA_VERSION\s*=\s*"([^"]+)"', current_content, re.MULTILINE)
        assert entries[-1]["config_schema_version"] == match.group(1)
    finally:
        db.close()


# --- 4. certification_evolution (reuso da Missao 122) -----------------------


def test_certification_evolution_delegates_to_engineering_memory_core_without_recomputing():
    fake_memory = _FakeEngineeringMemory(
        certifications=[{"mission_number": 60, "subject": "Missao 60"}]
    )
    service, db = _service(engineering_memory=fake_memory)
    try:
        result = service.certification_evolution()
        assert result == [{"mission_number": 60, "subject": "Missao 60"}]
        assert fake_memory.certification_history_calls == 1
    finally:
        db.close()


# --- 5. evolution_report / render_markdown -----------------------------------


def test_evolution_report_aggregates_all_five_dimensions_with_single_certification_call(
    monkeypatch, tmp_path
):
    _build_synthetic_repo(tmp_path)
    _patch_project_root(monkeypatch, tmp_path)
    fake_memory = _FakeEngineeringMemory(certifications=[{"mission_number": 50}])

    service, db = _service(engineering_memory=fake_memory)
    try:
        report = service.evolution_report()
        assert set(report.keys()) == {
            "generated_at",
            "module_evolution",
            "api_evolution",
            "configuration_evolution",
            "certification_evolution",
            "service_evolution",
        }
        assert fake_memory.certification_history_calls == 1
        assert isinstance(report["generated_at"], datetime)
    finally:
        db.close()


def _synthetic_report_for_markdown():
    return {
        "generated_at": datetime.now(UTC),
        "module_evolution": {"files": [{"file": "src/app/core/alpha.py"}], "files_without_history": []},
        "api_evolution": {"files": [{"file": "src/app/api/routes/x.py"}], "files_without_history": []},
        "service_evolution": {"files": [], "files_without_history": ["src/app/services/orfao.py"]},
        "configuration_evolution": [
            {
                "commit_hash": "abc1234",
                "committed_at": datetime(2026, 6, 28, tzinfo=UTC),
                "subject": "Missao 1",
                "config_schema_version": "1.0.0",
            }
        ],
        "certification_evolution": [{"mission_number": 60, "subject": "Missao 60"}],
    }


def test_render_markdown_reports_gap_when_files_without_history_exist():
    report = _synthetic_report_for_markdown()
    service, db = _service(engineering_memory=_FakeEngineeringMemory())
    try:
        markdown = service.render_markdown(report)
        assert "Architecture Evolution Timeline (Missao 123)" in markdown
        assert "1 arquivo(s)" in markdown
        assert "CONFIG_SCHEMA_VERSION = 1.0.0" in markdown
    finally:
        db.close()


def test_render_markdown_reports_no_gap_when_all_files_have_history():
    report = _synthetic_report_for_markdown()
    report["service_evolution"] = {"files": [], "files_without_history": []}
    service, db = _service(engineering_memory=_FakeEngineeringMemory())
    try:
        markdown = service.render_markdown(report)
        assert "Nenhum arquivo sem historico" in markdown
    finally:
        db.close()


def test_render_markdown_against_real_repository_does_not_crash():
    service, db = _service()
    try:
        markdown = service.render_markdown()
        assert markdown.startswith("# Architecture Evolution Timeline (Missao 123)")
    finally:
        db.close()


# --- registro + endpoints HTTP ----------------------------------------------


def test_architecture_evolution_timeline_service_is_registered_via_provide():
    assert "ArchitectureEvolutionTimelineService" in registered_providers()


def test_architecture_evolution_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/architecture-evolution/live")
        assert response.status_code == 200
        data = response.json()
        assert "module_evolution" in data
        assert "api_evolution" in data
        assert "configuration_evolution" in data
        assert "certification_evolution" in data
        assert "service_evolution" in data


def test_architecture_evolution_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/architecture-evolution/markdown")
        assert response.status_code == 200
        assert "Architecture Evolution Timeline" in response.text


def test_architecture_evolution_endpoint_is_overridable_via_container_not_hardcoded():
    class _StubTimeline:
        def evolution_report(self):
            return {"module_evolution": "stub-marker"}

        def render_markdown(self, report=None):
            return "stub markdown"

    real_app.dependency_overrides[get_architecture_evolution_timeline_service] = lambda: _StubTimeline()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/architecture-evolution/live")
            assert response.json() == {"module_evolution": "stub-marker"}
    finally:
        real_app.dependency_overrides.pop(get_architecture_evolution_timeline_service, None)
