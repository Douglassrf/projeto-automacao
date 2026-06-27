"""Missão 42 — Gerenciador Inteligente de Filas.

Cobre: backoff exponencial deterministico, claim() respeitando next_attempt_at,
requeue_dead_letter(), health_report() (stuck/starving/unhealthy_queues),
novos endpoints (/queue/health, /queue/jobs/{id}/requeue), payload atualizado
de /queue/stats, e as novas regras de validate_settings()/CONFIG_SCHEMA_VERSION.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.domain.models import QueueJob
from app.main import app
from app.services.queue_service import QueueService, compute_backoff_seconds

UTC = timezone.utc


# ---------------------------------------------------------------------------
# compute_backoff_seconds() - puro, deterministico
# ---------------------------------------------------------------------------


def test_backoff_grows_exponentially_with_attempts():
    base = compute_backoff_seconds(attempts=1, job_id=1, base_seconds=5, max_seconds=300)
    second = compute_backoff_seconds(attempts=2, job_id=1, base_seconds=5, max_seconds=300)
    third = compute_backoff_seconds(attempts=3, job_id=1, base_seconds=5, max_seconds=300)
    # attempt 1: 5*2^0=5 + jitter(1%5=1) = 6
    # attempt 2: 5*2^1=10 + jitter(1) = 11
    # attempt 3: 5*2^2=20 + jitter(1) = 21
    assert base == 6.0
    assert second == 11.0
    assert third == 21.0
    assert base < second < third


def test_backoff_is_deterministic_for_same_inputs():
    first_call = compute_backoff_seconds(attempts=4, job_id=77, base_seconds=5, max_seconds=300)
    second_call = compute_backoff_seconds(attempts=4, job_id=77, base_seconds=5, max_seconds=300)
    assert first_call == second_call


def test_backoff_jitter_differs_by_job_id_but_stays_bounded():
    delay_a = compute_backoff_seconds(attempts=1, job_id=10, base_seconds=5, max_seconds=300)
    delay_b = compute_backoff_seconds(attempts=1, job_id=11, base_seconds=5, max_seconds=300)
    # jitter = job_id % base_seconds -> 10%5=0, 11%5=1
    assert delay_a == 5.0
    assert delay_b == 6.0


def test_backoff_respects_max_seconds_ceiling():
    delay = compute_backoff_seconds(attempts=20, job_id=1, base_seconds=5, max_seconds=300)
    assert delay == 300.0


def test_backoff_handles_zero_base_seconds_without_dividing_by_zero():
    # base_seconds=0 nao deve lançar ZeroDivisionError no modulo do jitter.
    delay = compute_backoff_seconds(attempts=3, job_id=42, base_seconds=0, max_seconds=300)
    assert delay == 0.0


def test_backoff_treats_attempts_below_one_as_one():
    delay_zero = compute_backoff_seconds(attempts=0, job_id=1, base_seconds=5, max_seconds=300)
    delay_one = compute_backoff_seconds(attempts=1, job_id=1, base_seconds=5, max_seconds=300)
    assert delay_zero == delay_one


# ---------------------------------------------------------------------------
# fail() define next_attempt_at; claim() respeita o backoff
# ---------------------------------------------------------------------------


def test_fail_with_retry_sets_future_next_attempt_at():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=3)
        claimed = service.claim(queue_name=queue_name)[0]
        before = datetime.now(UTC)
        failed = service.fail(claimed.id, "erro transitorio", retry=True)
        assert failed.status == "retry"
        assert failed.next_attempt_at is not None
        assert failed.next_attempt_at.replace(tzinfo=UTC) > before
    finally:
        db.close()


def test_fail_to_dead_clears_next_attempt_at():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=1)
        claimed = service.claim(queue_name=queue_name)[0]
        failed = service.fail(claimed.id, "fatal", retry=True)
        assert failed.status == "dead"
        assert failed.next_attempt_at is None
    finally:
        db.close()


def test_claim_does_not_reclaim_retry_job_before_backoff_expires():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=3)
        claimed = service.claim(queue_name=queue_name)[0]
        service.fail(claimed.id, "erro", retry=True)

        # next_attempt_at está no futuro (backoff >= 5s pelo default) - claim()
        # não deve devolver este job agora.
        immediate = service.claim(queue_name=queue_name)
        assert immediate == []
    finally:
        db.close()


def test_claim_reclaims_retry_job_once_backoff_expires():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=3)
        claimed = service.claim(queue_name=queue_name)[0]
        failed = service.fail(claimed.id, "erro", retry=True)

        # Simula o backoff já ter expirado, sem precisar dormir no teste.
        row = db.get(QueueJob, failed.id)
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

        reclaimed = service.claim(queue_name=queue_name)
        assert len(reclaimed) == 1
        assert reclaimed[0].id == job.id
        assert reclaimed[0].status == "running"
    finally:
        db.close()


def test_claim_reclaims_retry_job_with_null_next_attempt_at():
    # Jobs criados antes da Missao 42 (coluna NULL via migracao) nao devem
    # ficar presos para sempre - None significa "sem restricao de backoff".
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=3)
        row = db.get(QueueJob, job.id)
        row.status = "retry"
        row.next_attempt_at = None
        db.commit()

        reclaimed = service.claim(queue_name=queue_name)
        assert len(reclaimed) == 1
        assert reclaimed[0].id == job.id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# requeue_dead_letter()
# ---------------------------------------------------------------------------


def test_requeue_dead_letter_resets_attempts_by_default():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=1)
        claimed = service.claim(queue_name=queue_name)[0]
        dead = service.fail(claimed.id, "fatal", retry=True)
        assert dead.status == "dead"

        requeued = service.requeue_dead_letter(dead.id)
        assert requeued.status == "queued"
        assert requeued.attempts == 0
        assert requeued.next_attempt_at is None
        assert requeued.locked_by == ""
        assert "[reenviado manualmente]" in requeued.error_message
    finally:
        db.close()


def test_requeue_dead_letter_can_preserve_attempts():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=1)
        claimed = service.claim(queue_name=queue_name)[0]
        dead = service.fail(claimed.id, "fatal", retry=True)

        requeued = service.requeue_dead_letter(dead.id, reset_attempts=False)
        assert requeued.attempts == dead.attempts
    finally:
        db.close()


def test_requeue_dead_letter_rejects_non_dead_job():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=3)
        with pytest.raises(ValueError):
            service.requeue_dead_letter(job.id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# health_report()
# ---------------------------------------------------------------------------


def test_health_report_detects_stuck_running_job():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={})
        claimed = service.claim(queue_name=queue_name)[0]

        row = db.get(QueueJob, claimed.id)
        lock_timeout = service.settings.queue_lock_timeout_seconds
        row.locked_at = datetime.now(UTC) - timedelta(seconds=lock_timeout + 60)
        db.commit()

        report = service.health_report()
        stuck_ids = {item["id"] for item in report["stuck_jobs"]}
        assert job.id in stuck_ids
        assert report["healthy"] is False
        assert any("travado" in warning for warning in report["warnings"])
    finally:
        db.close()


def test_health_report_detects_starving_queued_job():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={})

        row = db.get(QueueJob, job.id)
        starvation = service.settings.queue_starvation_threshold_seconds
        row.created_at = datetime.now(UTC) - timedelta(seconds=starvation + 60)
        db.commit()

        report = service.health_report()
        starving_ids = {item["id"] for item in report["starving_jobs"]}
        assert job.id in starving_ids
        assert report["healthy"] is False
        assert any("inanicao" in warning for warning in report["warnings"])
    finally:
        db.close()


def test_health_report_flags_queue_with_high_failure_rate():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        # Amostra de 5 jobs finalizados: 4 dead, 1 done -> taxa de falha 80% > 50% (default).
        for _ in range(4):
            job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=1)
            claimed = service.claim(queue_name=queue_name)[0]
            service.fail(claimed.id, "erro", retry=True)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={})
        claimed = service.claim(queue_name=queue_name)[0]
        service.complete(claimed.id, {})

        report = service.health_report()
        assert queue_name in report["unhealthy_queues"]
        assert report["healthy"] is False
    finally:
        db.close()


def test_health_report_ignores_small_samples_for_failure_rate():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        # Só 1 job, morto -> 100% de falha, mas abaixo da amostra mínima (5).
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={}, max_attempts=1)
        claimed = service.claim(queue_name=queue_name)[0]
        service.fail(claimed.id, "erro", retry=True)

        report = service.health_report()
        assert queue_name not in report["unhealthy_queues"]
    finally:
        db.close()


def test_health_report_healthy_when_no_issues():
    queue_name = f"m42-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        service = QueueService(db)
        job = service.enqueue(queue_name=queue_name, job_type="t", payload={})
        claimed = service.claim(queue_name=queue_name)[0]
        service.complete(claimed.id, {})

        report = service.health_report()
        assert queue_name not in report["unhealthy_queues"]
        # Não afirmamos report["healthy"] is True aqui pois outros testes no
        # mesmo banco de sessão podem ter deixado jobs travados/starving em
        # outras filas - isolamos por per_queue em vez disso.
        assert report["per_queue"].get(queue_name, {}).get("done") == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API: /queue/stats, /queue/health, /queue/jobs/{id}/requeue
# ---------------------------------------------------------------------------


def test_stats_endpoint_includes_healthy_and_warnings():
    with TestClient(app) as client:
        client.post("/api/v1/queue/jobs", json={"queue_name": "default", "job_type": "t", "payload": {}})
        response = client.get("/api/v1/queue/stats")
        assert response.status_code == 200
        data = response.json()
        assert "healthy" in data
        assert "warnings" in data
        assert isinstance(data["warnings"], list)


def test_health_endpoint_returns_expected_shape():
    with TestClient(app) as client:
        response = client.get("/api/v1/queue/health")
        assert response.status_code == 200
        data = response.json()
        for key in ("healthy", "stuck_jobs", "starving_jobs", "unhealthy_queues", "per_queue", "warnings"):
            assert key in data


def test_requeue_endpoint_via_api():
    queue_name = f"m42-{uuid4().hex[:8]}"
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/queue/jobs",
            json={"queue_name": queue_name, "job_type": "t", "payload": {}, "max_attempts": 1},
        ).json()
        claimed = client.post(
            "/api/v1/queue/jobs/claim", json={"queue_name": queue_name, "worker_id": "w1", "limit": 1}
        ).json()[0]
        dead = client.post(
            f"/api/v1/queue/jobs/{claimed['id']}/fail", json={"error_message": "fatal", "retry": True}
        ).json()
        assert dead["status"] == "dead"

        requeued = client.post(f"/api/v1/queue/jobs/{dead['id']}/requeue", json={"reset_attempts": True})
        assert requeued.status_code == 200
        assert requeued.json()["status"] == "queued"
        assert requeued.json()["attempts"] == 0


def test_requeue_endpoint_rejects_non_dead_job_with_400():
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/queue/jobs", json={"queue_name": "default", "job_type": "t", "payload": {}}
        ).json()
        response = client.post(f"/api/v1/queue/jobs/{created['id']}/requeue", json={})
        assert response.status_code == 400


def test_job_response_exposes_next_attempt_at_field():
    queue_name = f"m42-{uuid4().hex[:8]}"
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/queue/jobs", json={"queue_name": queue_name, "job_type": "t", "payload": {}}
        ).json()
        assert "next_attempt_at" in created
        assert created["next_attempt_at"] is None


# ---------------------------------------------------------------------------
# Config: schema version + novas regras de validação (Missão 42)
# ---------------------------------------------------------------------------


def test_config_schema_version_bumped_for_mission_42():
    assert CONFIG_SCHEMA_VERSION == "1.1.0"


def test_validate_settings_rejects_backoff_base_below_one():
    settings = get_settings()
    previous = settings.queue_retry_backoff_base_seconds
    settings.queue_retry_backoff_base_seconds = 0
    try:
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("queue_retry_backoff_base_seconds" in issue for issue in issues)
    finally:
        settings.queue_retry_backoff_base_seconds = previous


def test_validate_settings_rejects_max_backoff_below_base():
    settings = get_settings()
    previous_base = settings.queue_retry_backoff_base_seconds
    previous_max = settings.queue_retry_backoff_max_seconds
    settings.queue_retry_backoff_base_seconds = 100
    settings.queue_retry_backoff_max_seconds = 10
    try:
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("queue_retry_backoff_max_seconds" in issue for issue in issues)
    finally:
        settings.queue_retry_backoff_base_seconds = previous_base
        settings.queue_retry_backoff_max_seconds = previous_max


def test_validate_settings_rejects_starvation_threshold_below_one():
    settings = get_settings()
    previous = settings.queue_starvation_threshold_seconds
    settings.queue_starvation_threshold_seconds = 0
    try:
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("queue_starvation_threshold_seconds" in issue for issue in issues)
    finally:
        settings.queue_starvation_threshold_seconds = previous


@pytest.mark.parametrize("invalid_rate", [0.0, -0.1, 1.1, 2.0])
def test_validate_settings_rejects_failure_rate_out_of_range(invalid_rate):
    settings = get_settings()
    previous = settings.queue_failure_rate_threshold
    settings.queue_failure_rate_threshold = invalid_rate
    try:
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert any("queue_failure_rate_threshold" in issue for issue in issues)
    finally:
        settings.queue_failure_rate_threshold = previous


def test_validate_settings_accepts_default_backoff_config():
    settings = get_settings()
    issues = validate_settings(settings, Environment.DEVELOPMENT)
    backoff_issues = [issue for issue in issues if "backoff" in issue or "starvation" in issue or "failure_rate" in issue]
    assert backoff_issues == []
