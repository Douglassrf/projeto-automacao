"""Missao 45 - Gerenciamento de Recursos.

Contraparte de acao da Missao 44 (Diagnostico Automatico, somente leitura):
aqui o ResourceManagerService de fato libera recursos.

Cobre: disk_usage_report() sobre os diretorios de saida gerenciados,
purge_old_queue_jobs() (apaga apenas jobs terminais done/dead mais antigos
que o limite, nunca toca em queued/running/retry), purge_expired_cache()
(delegacao para CacheService.purge_expired() da Missao 43), run_cleanup()
(varredura combinada), os novos endpoints /resources/* e as novas regras de
validate_settings()/CONFIG_SCHEMA_VERSION (Missao 45).

Os testes de purge usam um queue_name unico por teste (via uuid) e
consultam jobs por id/queue_name especificos em vez de contagens absolutas
da tabela - o banco de dev/teste e compartilhado e acumula jobs residuais
de outras suites (o mesmo problema documentado na Missao 44), entao
qualquer asserção teria que ser relativa a dados proprios do teste, nunca
ao total da tabela.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.domain.models import QueueJob
from app.main import app
from app.services.resource_manager_service import ResourceManagerService, _dir_stats
from app.services import resource_manager_service as resource_manager_module

UTC = timezone.utc


def _qname() -> str:
    return f"m45-{uuid4().hex[:8]}"


def _make_job(db, *, queue_name: str, status: str, age_days: float | None = None) -> QueueJob:
    job = QueueJob(queue_name=queue_name, job_type="noop", status=status, payload_json="{}")
    db.add(job)
    db.commit()
    db.refresh(job)
    if age_days is not None:
        old_time = datetime.now(UTC) - timedelta(days=age_days)
        db.query(QueueJob).filter(QueueJob.id == job.id).update({"updated_at": old_time})
        db.commit()
    return job


def _exists(db, job_id: int) -> bool:
    return db.query(QueueJob).filter(QueueJob.id == job_id).first() is not None


# ---------------------------------------------------------------------------
# purge_old_queue_jobs()
# ---------------------------------------------------------------------------


def test_purge_old_queue_jobs_deletes_old_terminal_job():
    db = SessionLocal()
    try:
        queue_name = _qname()
        job = _make_job(db, queue_name=queue_name, status="done", age_days=999)
        job_id = job.id  # captura antes do purge: apos o delete+commit, o
        # ORM expira o objeto e tentar ler job.id de novo levantaria
        # ObjectDeletedError (a linha de fato nao existe mais).
        result = ResourceManagerService(db).purge_old_queue_jobs(max_age_days=1)
        assert result["deleted"] >= 1
        assert not _exists(db, job_id)
    finally:
        db.close()


def test_purge_old_queue_jobs_keeps_recent_terminal_job():
    db = SessionLocal()
    try:
        queue_name = _qname()
        job = _make_job(db, queue_name=queue_name, status="done")  # updated_at = agora
        ResourceManagerService(db).purge_old_queue_jobs(max_age_days=30)
        assert _exists(db, job.id)
    finally:
        db.close()


def test_purge_old_queue_jobs_deletes_old_dead_job_too():
    db = SessionLocal()
    try:
        queue_name = _qname()
        job = _make_job(db, queue_name=queue_name, status="dead", age_days=999)
        job_id = job.id
        ResourceManagerService(db).purge_old_queue_jobs(max_age_days=1)
        assert not _exists(db, job_id)
    finally:
        db.close()


@pytest.mark.parametrize("active_status", ["queued", "running", "retry"])
def test_purge_old_queue_jobs_never_touches_active_statuses(active_status):
    db = SessionLocal()
    try:
        queue_name = _qname()
        job = _make_job(db, queue_name=queue_name, status=active_status, age_days=999)
        ResourceManagerService(db).purge_old_queue_jobs(max_age_days=1)
        # job ativo, mesmo "antigo", nunca e tocado pela limpeza - e trabalho
        # pendente, nao lixo.
        assert _exists(db, job.id)
    finally:
        db.close()


def test_purge_old_queue_jobs_defaults_to_settings_retention_when_no_override():
    db = SessionLocal()
    try:
        result = ResourceManagerService(db).purge_old_queue_jobs()
        assert result["max_age_days"] == get_settings().resource_job_retention_days
    finally:
        db.close()


def test_purge_old_queue_jobs_explicit_override_takes_precedence():
    db = SessionLocal()
    try:
        result = ResourceManagerService(db).purge_old_queue_jobs(max_age_days=7)
        assert result["max_age_days"] == 7
    finally:
        db.close()


def test_purge_old_queue_jobs_cutoff_is_valid_isoformat_in_the_past():
    db = SessionLocal()
    try:
        result = ResourceManagerService(db).purge_old_queue_jobs(max_age_days=5)
        cutoff = datetime.fromisoformat(result["cutoff"])
        assert cutoff < datetime.now(UTC)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# purge_expired_cache() - delegacao para CacheService (Missao 43)
# ---------------------------------------------------------------------------


def test_purge_expired_cache_delegates_to_cache_service(monkeypatch):
    db = SessionLocal()
    try:
        sentinel = 42

        def fake_purge_expired(self, *, namespace=None):
            return sentinel

        monkeypatch.setattr(resource_manager_module.CacheService, "purge_expired", fake_purge_expired)
        assert ResourceManagerService(db).purge_expired_cache() == sentinel
    finally:
        db.close()


# ---------------------------------------------------------------------------
# run_cleanup() - varredura combinada
# ---------------------------------------------------------------------------


def test_run_cleanup_combines_queue_and_cache_results(monkeypatch):
    db = SessionLocal()
    try:
        service = ResourceManagerService(db)
        monkeypatch.setattr(
            service,
            "purge_old_queue_jobs",
            lambda max_age_days=None: {"deleted": 3, "cutoff": "2026-01-01T00:00:00+00:00", "max_age_days": 30},
        )
        monkeypatch.setattr(service, "purge_expired_cache", lambda: 5)

        result = service.run_cleanup()
        assert result == {
            "queue_jobs_deleted": 3,
            "queue_cutoff": "2026-01-01T00:00:00+00:00",
            "cache_entries_purged": 5,
        }
    finally:
        db.close()


def test_run_cleanup_forwards_max_age_days_override(monkeypatch):
    db = SessionLocal()
    try:
        service = ResourceManagerService(db)
        received = {}

        def fake_purge_jobs(max_age_days=None):
            received["max_age_days"] = max_age_days
            return {"deleted": 0, "cutoff": "2026-01-01T00:00:00+00:00", "max_age_days": max_age_days}

        monkeypatch.setattr(service, "purge_old_queue_jobs", fake_purge_jobs)
        monkeypatch.setattr(service, "purge_expired_cache", lambda: 0)

        service.run_cleanup(max_age_days=9)
        assert received["max_age_days"] == 9
    finally:
        db.close()


# ---------------------------------------------------------------------------
# disk_usage_report()
# ---------------------------------------------------------------------------


def test_disk_usage_report_has_expected_directory_keys():
    db = SessionLocal()
    try:
        report = ResourceManagerService(db).disk_usage_report()
        assert set(report["directories"].keys()) == {
            "campaign_kits",
            "orchestration_runs",
            "ugc",
            "premium_renders",
        }
    finally:
        db.close()


def test_disk_usage_report_entry_shape():
    db = SessionLocal()
    try:
        report = ResourceManagerService(db).disk_usage_report()
        entry = report["directories"]["campaign_kits"]
        assert set(entry.keys()) == {"path", "size_mb", "file_count"}
        assert isinstance(entry["size_mb"], float)
        assert isinstance(entry["file_count"], int)
    finally:
        db.close()


def test_disk_usage_report_total_is_sum_of_individual_directories():
    db = SessionLocal()
    try:
        report = ResourceManagerService(db).disk_usage_report()
        expected_total = round(sum(d["size_mb"] for d in report["directories"].values()), 2)
        assert abs(report["total_size_mb"] - expected_total) < 0.01
    finally:
        db.close()


def test_dir_stats_returns_zero_for_nonexistent_path():
    size_mb, file_count = _dir_stats(Path("/this/path/does/not/exist/m45"))
    assert size_mb == 0.0
    assert file_count == 0


def test_dir_stats_counts_real_files(tmp_path):
    # >1 MB por arquivo para que o tamanho arredondado a 2 casas decimais
    # nao colapse para 0.0 (arquivos de poucos KB arredondariam para 0.0).
    (tmp_path / "a.txt").write_bytes(b"x" * (2 * 1024 * 1024))
    (tmp_path / "b.txt").write_bytes(b"y" * (2 * 1024 * 1024))
    size_mb, file_count = _dir_stats(tmp_path)
    assert file_count == 2
    assert size_mb > 0.0


# ---------------------------------------------------------------------------
# API: /resources/*
# ---------------------------------------------------------------------------


def test_disk_usage_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.get("/api/v1/resources/disk-usage")
    assert response.status_code == 200
    body = response.json()
    assert "total_size_mb" in body
    assert "directories" in body


def test_cleanup_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.post("/api/v1/resources/cleanup")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"queue_jobs_deleted", "queue_cutoff", "cache_entries_purged"}


def test_purge_queue_jobs_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.post("/api/v1/resources/queue-jobs/purge", params={"max_age_days": 30})
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"deleted", "cutoff", "max_age_days"}
    assert body["max_age_days"] == 30


def test_purge_queue_jobs_endpoint_rejects_max_age_days_below_one():
    client = TestClient(app)
    response = client.post("/api/v1/resources/queue-jobs/purge", params={"max_age_days": 0})
    assert response.status_code == 422


def test_cleanup_endpoint_accepts_max_age_days_override():
    client = TestClient(app)
    response = client.post("/api/v1/resources/cleanup", params={"max_age_days": 10})
    assert response.status_code == 200
    assert response.json()["queue_cutoff"] is not None


# ---------------------------------------------------------------------------
# Configuracao - versionamento e validacao (Missao 45)
# ---------------------------------------------------------------------------


def test_config_schema_version_bumped_for_mission_45():
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (1, 4, 0)


def test_validate_settings_rejects_retention_below_one():
    settings = get_settings()
    previous = settings.resource_job_retention_days
    try:
        settings.resource_job_retention_days = 0
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("resource_job_retention_days" in issue for issue in issues)
    finally:
        settings.resource_job_retention_days = previous


def test_validate_settings_accepts_default_resource_config():
    settings = get_settings()
    issues = validate_settings(settings, Environment.DEVELOPMENT)
    assert not any("resource_job_retention_days" in issue for issue in issues)
