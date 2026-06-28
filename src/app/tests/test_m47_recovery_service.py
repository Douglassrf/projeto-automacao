"""Missao 47 - Testes de Recuperacao.

Contraparte de ACAO do health_report() da fila (Missao 42, somente
leitura). health_report() detecta jobs travados em status="running" alem
do lock timeout, mas o proprio docstring documenta a limitacao: esses
jobs "serao reclamados no proximo claim()" - se nenhum worker estiver
puxando a fila naquele momento, o job fica parado indefinidamente.
RecoveryService.recover_stale_running_jobs() age agora, sem esperar pelo
proximo claim().

Cobre: recovery_report() (somente leitura, reusa health_report()),
recover_stale_running_jobs() (recupera para "retry" com tentativas
restantes, para "dead" sem tentativas restantes, ignora jobs nao
travados, respeita o limite de sweep), os novos endpoints /recovery/* e
as novas regras de validate_settings()/CONFIG_SCHEMA_VERSION (Missao 47).
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.domain.models import QueueJob
from app.main import app
from app.services.recovery_service import RecoveryService

UTC = timezone.utc


def _queue_name() -> str:
    return f"m47-queue-{uuid4().hex[:8]}"


def _make_stuck_job(db, *, queue_name: str, attempts: int, max_attempts: int, locked_seconds_ago: int) -> QueueJob:
    """Cria um job ja em status='running', travado ha `locked_seconds_ago`
    segundos - simula um worker que morreu sem chamar complete()/fail()."""
    job = QueueJob(
        queue_name=queue_name,
        job_type="m47-test-job",
        status="running",
        attempts=attempts,
        max_attempts=max_attempts,
        locked_by="worker-que-morreu",
        locked_at=datetime.now(UTC) - timedelta(seconds=locked_seconds_ago),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# recover_stale_running_jobs() - recuperacao para retry
# ---------------------------------------------------------------------------


def test_recover_stale_running_job_with_attempts_left_goes_to_retry():
    db = SessionLocal()
    try:
        settings = get_settings()
        queue_name = _queue_name()
        job = _make_stuck_job(
            db,
            queue_name=queue_name,
            attempts=1,
            max_attempts=3,
            locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
        )
        job_id = job.id
        service = RecoveryService(db)
        result = service.recover_stale_running_jobs()

        assert job_id in [j["id"] for j in result["recovered_to_retry"]]
        refreshed = db.query(QueueJob).filter(QueueJob.id == job_id).first()
        assert refreshed.status == "retry"
        assert refreshed.locked_by == ""
        assert refreshed.locked_at is None
        assert refreshed.next_attempt_at is not None
        assert "Recuperado automaticamente" in refreshed.error_message
    finally:
        db.close()


def test_recover_stale_running_job_without_attempts_left_goes_to_dead():
    db = SessionLocal()
    try:
        settings = get_settings()
        queue_name = _queue_name()
        job = _make_stuck_job(
            db,
            queue_name=queue_name,
            attempts=3,
            max_attempts=3,
            locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
        )
        job_id = job.id
        service = RecoveryService(db)
        result = service.recover_stale_running_jobs()

        assert job_id in [j["id"] for j in result["recovered_to_dead"]]
        refreshed = db.query(QueueJob).filter(QueueJob.id == job_id).first()
        assert refreshed.status == "dead"
        assert refreshed.next_attempt_at is None
        assert refreshed.locked_by == ""
    finally:
        db.close()


# ---------------------------------------------------------------------------
# recover_stale_running_jobs() - nao toca o que nao deveria
# ---------------------------------------------------------------------------


def test_recover_does_not_touch_running_job_within_lock_timeout():
    db = SessionLocal()
    try:
        queue_name = _queue_name()
        job = _make_stuck_job(
            db, queue_name=queue_name, attempts=1, max_attempts=3, locked_seconds_ago=5,
        )
        job_id = job.id
        service = RecoveryService(db)
        result = service.recover_stale_running_jobs()

        all_recovered_ids = [j["id"] for j in result["recovered_to_retry"] + result["recovered_to_dead"]]
        assert job_id not in all_recovered_ids
        refreshed = db.query(QueueJob).filter(QueueJob.id == job_id).first()
        assert refreshed.status == "running"
    finally:
        db.close()


def test_recover_does_not_touch_queued_or_done_jobs():
    db = SessionLocal()
    try:
        queue_name = _queue_name()
        queued = QueueJob(queue_name=queue_name, job_type="m47-test-job", status="queued")
        done = QueueJob(queue_name=queue_name, job_type="m47-test-job", status="done")
        db.add_all([queued, done])
        db.commit()
        queued_id, done_id = queued.id, done.id

        service = RecoveryService(db)
        result = service.recover_stale_running_jobs()

        all_recovered_ids = [j["id"] for j in result["recovered_to_retry"] + result["recovered_to_dead"]]
        assert queued_id not in all_recovered_ids
        assert done_id not in all_recovered_ids
    finally:
        db.close()


# ---------------------------------------------------------------------------
# recover_stale_running_jobs() - limite de sweep
# ---------------------------------------------------------------------------


def test_recover_respects_explicit_limit():
    db = SessionLocal()
    try:
        settings = get_settings()
        queue_name = _queue_name()
        for _ in range(4):
            _make_stuck_job(
                db,
                queue_name=queue_name,
                attempts=0,
                max_attempts=3,
                locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
            )
        service = RecoveryService(db)
        result = service.recover_stale_running_jobs(limit=2)

        assert result["found"] == 2
        assert result["more_pending"] is True
    finally:
        db.close()


def test_recover_uses_settings_default_limit_when_not_specified():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.recovery_max_jobs_per_sweep
    try:
        settings.recovery_max_jobs_per_sweep = 2
        queue_name = _queue_name()
        for _ in range(4):
            _make_stuck_job(
                db,
                queue_name=queue_name,
                attempts=0,
                max_attempts=3,
                locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
            )
        service = RecoveryService(db)
        result = service.recover_stale_running_jobs()
        assert result["found"] == 2
    finally:
        settings.recovery_max_jobs_per_sweep = previous
        db.close()


def test_recover_more_pending_is_false_when_everything_fits():
    db = SessionLocal()
    try:
        settings = get_settings()
        queue_name = _queue_name()
        _make_stuck_job(
            db,
            queue_name=queue_name,
            attempts=0,
            max_attempts=3,
            locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
        )
        service = RecoveryService(db)
        result = service.recover_stale_running_jobs(limit=50)
        assert result["more_pending"] is False
    finally:
        db.close()


def test_recover_returns_lock_timeout_seconds_used():
    db = SessionLocal()
    try:
        settings = get_settings()
        service = RecoveryService(db)
        result = service.recover_stale_running_jobs()
        assert result["lock_timeout_seconds"] == settings.queue_lock_timeout_seconds
    finally:
        db.close()


# ---------------------------------------------------------------------------
# recovery_report() - somente leitura
# ---------------------------------------------------------------------------


def test_recovery_report_counts_recoverable_now_from_stuck_jobs():
    db = SessionLocal()
    try:
        settings = get_settings()
        queue_name = _queue_name()
        _make_stuck_job(
            db,
            queue_name=queue_name,
            attempts=0,
            max_attempts=3,
            locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
        )
        service = RecoveryService(db)
        report = service.recovery_report()
        assert report["recoverable_now"] >= 1
        assert report["healthy"] is False
    finally:
        db.close()


def test_recovery_report_does_not_mutate_anything():
    db = SessionLocal()
    try:
        settings = get_settings()
        queue_name = _queue_name()
        job = _make_stuck_job(
            db,
            queue_name=queue_name,
            attempts=0,
            max_attempts=3,
            locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
        )
        job_id = job.id
        service = RecoveryService(db)
        service.recovery_report()

        refreshed = db.query(QueueJob).filter(QueueJob.id == job_id).first()
        assert refreshed.status == "running"
    finally:
        db.close()


def test_recovery_report_shape():
    db = SessionLocal()
    try:
        service = RecoveryService(db)
        report = service.recovery_report()
        assert set(report.keys()) == {
            "healthy",
            "recoverable_now",
            "requires_external_action",
            "warnings",
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API: /recovery/*
# ---------------------------------------------------------------------------


def test_report_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.get("/api/v1/recovery/report")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "healthy",
        "recoverable_now",
        "requires_external_action",
        "warnings",
    }


def test_sweep_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.post("/api/v1/recovery/sweep")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "swept_at",
        "lock_timeout_seconds",
        "found",
        "recovered_to_retry",
        "recovered_to_dead",
        "more_pending",
    }


def test_sweep_endpoint_actually_recovers_a_stuck_job():
    db = SessionLocal()
    try:
        settings = get_settings()
        queue_name = _queue_name()
        job = _make_stuck_job(
            db,
            queue_name=queue_name,
            attempts=0,
            max_attempts=3,
            locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
        )
        job_id = job.id
    finally:
        db.close()

    client = TestClient(app)
    response = client.post("/api/v1/recovery/sweep")
    assert response.status_code == 200
    body = response.json()
    recovered_ids = [j["id"] for j in body["recovered_to_retry"] + body["recovered_to_dead"]]
    assert job_id in recovered_ids


def test_sweep_endpoint_accepts_limit_query_param():
    client = TestClient(app)
    response = client.post("/api/v1/recovery/sweep", params={"limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["found"] <= 1


def test_sweep_endpoint_rejects_limit_below_one():
    client = TestClient(app)
    response = client.post("/api/v1/recovery/sweep", params={"limit": 0})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Configuracao - versionamento e validacao (Missao 47)
# ---------------------------------------------------------------------------


def test_config_schema_version_bumped_for_mission_47():
    parts = tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split("."))
    assert parts >= (1, 6, 0)


def test_validate_settings_rejects_recovery_max_jobs_per_sweep_below_one():
    settings = get_settings()
    previous = settings.recovery_max_jobs_per_sweep
    try:
        settings.recovery_max_jobs_per_sweep = 0
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("recovery_max_jobs_per_sweep" in issue for issue in issues)
    finally:
        settings.recovery_max_jobs_per_sweep = previous


def test_validate_settings_accepts_default_recovery_config():
    settings = get_settings()
    issues = validate_settings(settings, Environment.DEVELOPMENT)
    assert not any("recovery_max_jobs_per_sweep" in issue for issue in issues)
