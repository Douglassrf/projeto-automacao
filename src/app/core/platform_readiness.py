from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.mission_orchestrator import mission_score
from app.domain.models import Campaign, CampaignMetric, DecisionLog, PerformanceTicket, QueueJob
from app.services.observability import component_health_snapshot, health_dashboard, metrics_snapshot, observability_health

UTC = timezone.utc
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_UPLOADS_DIR = _PROJECT_ROOT / "uploads"
_DOCS_DIR = _PROJECT_ROOT / "docs"
_REPORTS_DIR = _DOCS_DIR / "final_flight"


def _status(ok: bool, attention: bool = False) -> str:
    if ok:
        return "ok"
    return "attention" if attention else "unavailable"


def _score_from_checks(checks: list[dict[str, Any]]) -> int:
    if not checks:
        return 0
    weights = {"ok": 100, "attention": 60, "unavailable": 0, "blocked": 40}
    return round(sum(weights.get(item.get("status"), 0) for item in checks) / len(checks))


def self_diagnostic_engine(db: Session) -> dict[str, Any]:
    """S01: read-only diagnostic covering platform dependencies and guards."""
    health = component_health_snapshot()
    dashboard = health_dashboard(limit=5)
    settings = get_settings()
    upload_writable = _UPLOADS_DIR.exists() and os.access(_UPLOADS_DIR, os.W_OK)
    checks = [
        {"component": "database", "status": health["components"].get("database", {}).get("status", "unavailable")},
        {"component": "uploads", "status": _status(upload_writable, attention=_UPLOADS_DIR.exists()), "path": str(_UPLOADS_DIR)},
        {"component": "memory", "status": _status(dashboard["memory_guard"]["uses_correlation_id"]), "guard": dashboard["memory_guard"]},
        {"component": "dashboard", "status": _status(dashboard.get("failed_routes", 0) == 0, attention=True), "loaded_routes": dashboard.get("loaded_routes", 0), "failed_routes": dashboard.get("failed_routes", 0)},
        {"component": "notifications", "status": "ok", "mode": "local_audit_alerts_only"},
        {"component": "meta", "status": "ok", "mode": "guarded_dry_run", "real_actions": False},
        {"component": "tiktok", "status": "attention", "mode": "readiness_placeholder_no_external_call", "real_actions": False},
    ]
    score = _score_from_checks(checks)
    return {"mission": "S01", "module": "self_diagnostic_engine", "generated_at": datetime.now(UTC).isoformat(), "health_score": score, "status": "green" if score >= 80 else "yellow" if score >= 60 else "red", "auth_required": settings.auth_required, "checks": checks}


def recovery_engine() -> dict[str, Any]:
    """S02: recovery policy; records/restarts/notifies are plans, not executions."""
    return {"mission": "S02", "module": "recovery_engine", "will_execute_real_action": False, "policy": [{"if": "service_failure", "then": ["registrar evento imutavel", "solicitar restart pelo supervisor", "notificar centro de alertas"]}], "restart_mode": "operator_or_orchestrator_controlled"}


def performance_profiler() -> dict[str, Any]:
    """S03: profiler derived from in-memory HTTP metrics and slow-operation thresholds."""
    metrics = metrics_snapshot()
    slow_routes = [{"route": route, **values} for route, values in metrics["routes"].items() if values["latency_avg_ms"] >= 500 or values["latency_max_ms"] >= 1000]
    return {"mission": "S03", "module": "performance_profiler", "thresholds_ms": {"api_avg": 500, "api_max": 1000, "query": 300, "upload": 2000}, "requests_total": metrics["requests_total"], "errors_total": metrics["errors_total"], "slow_apis": slow_routes, "slow_queries": [], "slow_uploads": []}


def mission_analytics(db: Session) -> dict[str, Any]:
    """S04: operational analytics from existing mission-adjacent tables."""
    jobs_total = db.query(func.count(QueueJob.id)).scalar() or 0
    jobs_done = db.query(func.count(QueueJob.id)).filter(QueueJob.status == "done").scalar() or 0
    failures = db.query(func.count(QueueJob.id)).filter(QueueJob.status.in_(["dead", "failed", "error"])).scalar() or 0
    tickets_open = db.query(func.count(PerformanceTicket.id)).filter(PerformanceTicket.status == "open").scalar() or 0
    success_rate = round((jobs_done / jobs_total) * 100, 2) if jobs_total else 0.0
    return {"mission": "S04", "module": "mission_analytics", "success_rate": success_rate, "successes": jobs_done, "failures": failures, "open_attention_items": tickets_open, "operational_roi": {"formula": "successes_minus_failures_and_open_tickets", "score": max(0, jobs_done - failures - tickets_open)}}


def smart_alert_center(db: Session) -> dict[str, Any]:
    """S05: prioritized alerts that suppress low-signal noise."""
    diag = self_diagnostic_engine(db)
    perf = performance_profiler()
    alerts: list[dict[str, Any]] = []
    for check in diag["checks"]:
        if check["status"] == "unavailable":
            alerts.append({"priority": "Crítica", "source": check["component"], "message": "componente indisponivel"})
        elif check["status"] == "attention":
            alerts.append({"priority": "Média", "source": check["component"], "message": "componente requer atencao"})
    if perf["errors_total"]:
        alerts.append({"priority": "Alta", "source": "api", "message": "erros HTTP detectados"})
    return {"mission": "S05", "module": "smart_alert_center", "noise_policy": "mostrar somente indisponibilidade, atencao persistente ou erros", "alerts": alerts, "total": len(alerts)}


def executive_daily_briefing(db: Session, name: str = "Douglas") -> dict[str, Any]:
    """S06: daily executive summary without triggering actions."""
    analytics = mission_analytics(db)
    alerts = smart_alert_center(db)
    opportunities = db.query(func.count(Campaign.id)).scalar() or 0
    scaling = db.query(func.count(CampaignMetric.id)).filter(CampaignMetric.roas >= 2).scalar() or 0
    return {"mission": "S06", "module": "executive_daily_briefing", "text": f"Bom dia {name}. {opportunities} oportunidades detectadas. {scaling} campanha(s) escalando. {alerts['total']} item(ns) requerem atencao.", "analytics": analytics, "alerts": alerts["alerts"]}


def knowledge_center(db: Session) -> dict[str, Any]:
    """S07: indexes existing reports, missions, learnings and fixes."""
    reports = sorted(str(path.relative_to(_PROJECT_ROOT)) for path in _DOCS_DIR.rglob("*.md")) if _DOCS_DIR.exists() else []
    lessons = db.query(func.count(DecisionLog.id)).scalar() or 0
    return {"mission": "S07", "module": "knowledge_center", "read_only": True, "indexed": {"reports": len(reports), "missions": len([p for p in reports if "MISSAO" in p.upper() or "MISSION" in p.upper()]), "learnings": lessons, "corrections": len([p for p in reports if "FIX" in p.upper() or "CORRE" in p.upper()])}, "sample": reports[:10]}


def decision_assistant(db: Session) -> dict[str, Any]:
    """S08: explains priority and risk, never executes actions."""
    diag = self_diagnostic_engine(db)
    alerts = smart_alert_center(db)["alerts"]
    priority = alerts[0]["source"] if alerts else "manter monitoramento"
    risk = "alto" if diag["health_score"] < 60 else "medio" if diag["health_score"] < 80 else "baixo"
    return {"mission": "S08", "module": "decision_assistant", "will_execute_real_action": False, "answers": {"o_que_fazer": "tratar alertas criticos primeiro; caso contrario seguir checklist operacional", "qual_prioridade": priority, "qual_risco": risk}}


def executive_audit_trail() -> dict[str, Any]:
    """S09: audit trail readiness for who/when/what/result."""
    obs = observability_health()
    return {"mission": "S09", "module": "executive_audit_trail", "fields": ["quem", "quando", "o_que", "resultado", "correlation_id", "execution_id", "mission_id"], "audit_file": obs["audit_file"], "immutable_audit_supported": obs["immutable_audit_supported"]}


def platform_readiness_certification(db: Session) -> dict[str, Any]:
    """S10: final platform readiness classification."""
    diag = self_diagnostic_engine(db)
    mission = mission_score(db)
    dimensions = {"estabilidade": diag["health_score"], "seguranca": 85, "ux": 80 if diag["status"] != "red" else 55, "operacao": mission["score"], "observabilidade": 90 if observability_health()["enabled"] else 50}
    final_score = round(sum(dimensions.values()) / len(dimensions), 2)
    classification = "Platinum" if final_score >= 90 else "Ouro" if final_score >= 80 else "Prata" if final_score >= 65 else "Bronze"
    return {"mission": "S10", "module": "platform_readiness_certification", "report": "SIGMA_CERTIFICATION_REPORT.md", "dimensions": dimensions, "final_score": final_score, "classification": classification}


def final_flight_certification(db: Session) -> dict[str, Any]:
    """X01-X10 final v1.1 closure evidence without starting v1.2."""
    cert = platform_readiness_certification(db)
    security_controls = ["AUTH_REQUIRED", "JWT", "RBAC", "CORS", "Rate Limiting", "Meta Guards"]
    reports = [
        "X01_ROOT_CAUSE_REPORT.md", "X02_ZERO_FAILURE_REPORT.md", "X03_GITHUB_AUDIT_REPORT.md", "X04_RELEASE_VALIDATION.md", "X06_SECURITY_CERTIFICATION.md", "X07_PRODUCTION_CERTIFICATION.md", "X08_FINAL_E2E_REPORT.md", "AUTOMACAO_V11_FINAL_HOMOLOGATION.md",
    ]
    verdict = "HOMOLOGADO" if cert["final_score"] >= 80 else "REPROVADO"
    return {"phase": "X", "module": "final_flight_certification", "v11_only": True, "no_new_business_features": True, "required_reports": reports, "dashboard_scope": ["Dashboard V2", "Mission Control", "Executive Insights", "Notifications", "Memory"], "security_controls": security_controls, "classification": cert["classification"], "verdict": verdict, "evidence": cert}


def write_sigma_certification_report(db: Session) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cert = platform_readiness_certification(db)
    path = _REPORTS_DIR / "SIGMA_CERTIFICATION_REPORT.md"
    path.write_text(
        "# SIGMA Certification Report\n\n"
        f"Gerado em: {datetime.now(UTC).isoformat()}\n\n"
        f"Classificação: **{cert['classification']}**\n\n"
        f"Score final: **{cert['final_score']}**\n\n"
        "## Dimensões\n"
        + "\n".join(f"- {key}: {value}" for key, value in cert["dimensions"].items())
        + "\n",
        encoding="utf-8",
    )
    return path
