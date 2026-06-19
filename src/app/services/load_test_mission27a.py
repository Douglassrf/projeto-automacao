from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.decision_feed_store import DecisionFeedStore
from app.services.observability import audit_event, log_event


DEFAULT_BATCHES = (10, 50, 100)
DEFAULT_TARGETS = (
    {"method": "GET", "path": "/health"},
    {"method": "GET", "path": "/api/v1/health"},
    {"method": "GET", "path": "/api/v1/observability/health"},
    {"method": "GET", "path": "/api/v1/observability/dashboard"},
    {"method": "POST", "path": "/api/v1/observability/audit"},
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _reports_dir() -> Path:
    path = _project_root() / "logs" / "load_tests"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 2)
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return round(ordered[lower], 2)
    weight = index - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


def _summarize_batch(batch_size: int, records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(item["latency_ms"]) for item in records]
    status_codes: dict[str, int] = {}
    for item in records:
        key = str(item.get("status_code"))
        status_codes[key] = status_codes.get(key, 0) + 1
    failures = [item for item in records if not item.get("ok")]
    missing_trace = [
        item for item in records
        if not item.get("response_correlation_id")
        or not item.get("response_execution_id")
        or not item.get("response_mission_id")
    ]
    return {
        "batch_size": batch_size,
        "total_requests": len(records),
        "successful_requests": len(records) - len(failures),
        "failed_requests": len(failures),
        "error_rate_percent": round((len(failures) / len(records)) * 100, 2) if records else 0.0,
        "trace_header_coverage_percent": round(((len(records) - len(missing_trace)) / len(records)) * 100, 2) if records else 0.0,
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else 0.0,
            "avg": round(statistics.mean(latencies), 2) if latencies else 0.0,
            "p95": _percentile(latencies, 0.95),
            "max": round(max(latencies), 2) if latencies else 0.0,
        },
        "status_codes": status_codes,
    }


def _request_payload(target: dict[str, str], index: int, mission_id: str, execution_id: str, correlation_id: str) -> dict[str, Any] | None:
    if target["method"] != "POST":
        return None
    return {
        "actor": "Mission27A",
        "action": "controlled_load_probe",
        "resource_type": "observability",
        "resource_id": f"request-{index}",
        "status": "ok",
        "mission_id": mission_id,
        "execution_id": execution_id,
        "correlation_id": correlation_id,
        "details": {"safe": True, "dry_run": True, "batch_probe": True},
    }


def _run_one_request(client: TestClient, target: dict[str, str], index: int, mission_id: str, batch_size: int) -> dict[str, Any]:
    correlation_id = f"corr_27a_{uuid4().hex}"
    execution_id = f"exec_27a_{uuid4().hex}"
    headers = {
        "x-correlation-id": correlation_id,
        "x-execution-id": execution_id,
        "x-mission-id": mission_id,
    }
    started = time.perf_counter()
    try:
        payload = _request_payload(target, index, mission_id, execution_id, correlation_id)
        if target["method"] == "POST":
            response = client.post(target["path"], json=payload, headers=headers)
        else:
            response = client.get(target["path"], headers=headers)
        latency_ms = (time.perf_counter() - started) * 1000
        ok = 200 <= response.status_code < 500
        return {
            "ok": ok,
            "method": target["method"],
            "path": target["path"],
            "batch_size": batch_size,
            "request_index": index,
            "status_code": response.status_code,
            "latency_ms": round(latency_ms, 2),
            "correlation_id": correlation_id,
            "execution_id": execution_id,
            "mission_id": mission_id,
            "response_correlation_id": response.headers.get("x-correlation-id"),
            "response_execution_id": response.headers.get("x-execution-id"),
            "response_mission_id": response.headers.get("x-mission-id"),
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return {
            "ok": False,
            "method": target["method"],
            "path": target["path"],
            "batch_size": batch_size,
            "request_index": index,
            "status_code": None,
            "latency_ms": round(latency_ms, 2),
            "correlation_id": correlation_id,
            "execution_id": execution_id,
            "mission_id": mission_id,
            "error": str(exc),
        }


def _run_batch(
    *,
    client: TestClient,
    batch_size: int,
    targets: tuple[dict[str, str], ...],
    mission_id: str,
    concurrency: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    workers = max(1, min(concurrency, batch_size))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for index in range(batch_size):
            target = targets[index % len(targets)]
            futures.append(executor.submit(_run_one_request, client, target, index + 1, mission_id, batch_size))
        for future in as_completed(futures):
            records.append(future.result())
    records.sort(key=lambda item: item["request_index"])
    summary = _summarize_batch(batch_size, records)
    summary["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    summary["concurrency"] = workers
    summary["records"] = records
    return summary


def run_mission27a_load_test(
    *,
    batches: tuple[int, ...] = DEFAULT_BATCHES,
    concurrency: int = 8,
    client_factory: Callable[[], TestClient] | None = None,
    mission_id: str = "27A",
    persist: bool = True,
) -> dict[str, Any]:
    """Executa carga local controlada em rotas seguras e registra aprendizado.

    Nao chama Meta, nao chama providers externos e nao executa producao real.
    """

    settings = get_settings()
    previous_auth_required = settings.auth_required
    started_at = datetime.now(UTC).isoformat()
    brain = CampaignBrainAgent()
    decision_feed = DecisionFeedStore()
    memory = CampaignMemoryStore()

    brain_review = brain.review_before_campaign({
        "product_name": "Projeto Automacao",
        "niche": "automacao multiagente",
        "campaign_stage": "MISSAO_27A_LOAD_TEST",
        "budget_brl": 0,
        "metrics": {"planned_batches": list(batches), "concurrency": concurrency},
        "offer": "Teste de carga controlado em Safe / Dry Run.",
    })
    decision_feed.record_brain_decision(brain_review, context={
        "product_name": "Projeto Automacao",
        "niche": "automacao multiagente",
        "campaign_stage": "MISSAO_27A_LOAD_TEST_PRE_REVIEW",
    })

    settings.auth_required = False
    try:
        if client_factory is None:
            from app.main import app

            client_factory = lambda: TestClient(app)

        with client_factory() as client:
            batch_results = [
                _run_batch(
                    client=client,
                    batch_size=batch_size,
                    targets=DEFAULT_TARGETS,
                    mission_id=mission_id,
                    concurrency=concurrency,
                )
                for batch_size in batches
            ]
    finally:
        settings.auth_required = previous_auth_required

    total_requests = sum(item["total_requests"] for item in batch_results)
    failed_requests = sum(item["failed_requests"] for item in batch_results)
    all_latencies = [
        record["latency_ms"]
        for batch in batch_results
        for record in batch["records"]
    ]
    trace_coverages = [item["trace_header_coverage_percent"] for item in batch_results]
    status = "approved" if failed_requests == 0 and min(trace_coverages or [0]) == 100 else "attention"
    finished_at = datetime.now(UTC).isoformat()

    report = {
        "mission": "27A",
        "title": "Teste de Carga Controlado",
        "status": status,
        "safe_mode": True,
        "dry_run": True,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_requests": total_requests,
        "failed_requests": failed_requests,
        "error_rate_percent": round((failed_requests / total_requests) * 100, 2) if total_requests else 0.0,
        "latency_ms": {
            "avg": round(statistics.mean(all_latencies), 2) if all_latencies else 0.0,
            "p95": _percentile(all_latencies, 0.95),
            "max": round(max(all_latencies), 2) if all_latencies else 0.0,
        },
        "trace_header_coverage_percent": round(statistics.mean(trace_coverages), 2) if trace_coverages else 0.0,
        "batches": [
            {key: value for key, value in batch.items() if key != "records"}
            for batch in batch_results
        ],
        "targets": DEFAULT_TARGETS,
        "brain_review": brain_review,
        "next_action": "Missao 28 - MinerEngine Real Controlado" if status == "approved" else "Corrigir gargalos antes da Missao 28",
    }

    report_path: Path | None = None
    if persist:
        report_path = _reports_dir() / f"mission27a_load_test_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps({**report, "raw_batches": batch_results}, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)

    audit_event(
        actor="Mission27A",
        action="controlled_load_test_completed",
        resource_type="observability",
        resource_id=report_path.name if report_path else "memory_only",
        status=status,
        mission_id=mission_id,
        details={
            "total_requests": total_requests,
            "failed_requests": failed_requests,
            "error_rate_percent": report["error_rate_percent"],
            "trace_header_coverage_percent": report["trace_header_coverage_percent"],
        },
    )
    log_event(
        "mission_27a_load_test",
        status="ok" if status == "approved" else "attention",
        details={
            "total_requests": total_requests,
            "failed_requests": failed_requests,
            "report_path": str(report_path) if report_path else None,
        },
        mission_id=mission_id,
    )
    memory.remember({
        "product_name": "Projeto Automacao",
        "niche": "automacao multiagente",
        "campaign_stage": "MISSAO_27A_LOAD_TEST",
        "outcome": status.upper(),
        "lesson": "Teste de carga controlado executado com Brain/Brian antes e memoria depois.",
        "learning": "Validar 10/50/100 execucoes antes de MinerEngine real; acompanhar erro, latencia e trace headers.",
        "metrics": {
            "total_requests": total_requests,
            "failed_requests": failed_requests,
            "error_rate_percent": report["error_rate_percent"],
            "latency_p95_ms": report["latency_ms"]["p95"],
            "trace_header_coverage_percent": report["trace_header_coverage_percent"],
        },
        "source": "Mission27ALoadTest",
        "output_file": str(report_path) if report_path else None,
    })

    return report
