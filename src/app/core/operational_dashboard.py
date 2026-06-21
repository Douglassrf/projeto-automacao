from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.real_connectors_readiness import CONNECTOR_REQUIREMENTS
from app.core.security_status import security_hardening_status
from app.domain.models import Campaign, MetaActionRequest, PerformanceTicket, QueueJob
from app.services.observability import health_dashboard, immutable_audit_health, observability_health
from app.services.queue_service import QueueService


def _counts_by_status(db: Session, model: Any) -> dict[str, int]:
    rows = db.query(model.status, func.count(model.id)).group_by(model.status).all()
    return {str(status): int(count) for status, count in rows}


def operational_dashboard_snapshot(db: Session) -> dict[str, Any]:
    """Read-only executive dashboard for operational security and pending work."""
    settings = get_settings()
    security = security_hardening_status()
    observability = observability_health()
    audit = immutable_audit_health()
    route_health = health_dashboard(limit=5)
    queue = QueueService(db).stats()
    connectors = {
        "status": "readiness_only",
        "network_access_used": False,
        "credentials_loaded": False,
        "blocked_reasons": [],
        "connectors": [
            {
                "platform": name,
                "status": "readiness_only",
                "requirements": requirements,
                "network_enabled": False,
                "credentials_loaded": False,
                "real_write_enabled": False,
                "sandbox_required": True,
            }
            for name, requirements in sorted(CONNECTOR_REQUIREMENTS.items())
        ],
    }

    campaign_status = _counts_by_status(db, Campaign)
    ticket_status = _counts_by_status(db, PerformanceTicket)
    action_status = _counts_by_status(db, MetaActionRequest)
    queue_status = _counts_by_status(db, QueueJob)

    pending_approvals = int(action_status.get("pending_approval", 0))
    active_blockers = sorted(
        set(connectors.get("blocked_reasons", []))
        | ({"auth_required_disabled"} if not settings.auth_required else set())
        | ({"meta_real_mode_unlocked"} if not settings.meta_dry_run else set())
        | ({"meta_manual_confirmation_disabled"} if not settings.meta_require_manual_confirmation else set())
        | ({"api_route_load_failures"} if route_health.get("failed_routes") else set())
    )

    return {
        "status": "attention" if active_blockers or pending_approvals else "ok",
        "mode": {
            "dry_run": bool(settings.meta_dry_run),
            "real_mode_enabled": not bool(settings.meta_dry_run),
            "auth_required": bool(settings.auth_required),
            "manual_confirmation_required": bool(settings.meta_require_manual_confirmation),
            "autopublish_enabled": bool(settings.meta_autopublish),
            "read_only_dashboard": True,
        },
        "security": {
            "status": security["status"],
            "controls": security["controls"],
            "real_execution_policy": security["real_execution_policy"],
        },
        "queues": {"summary": queue, "by_status": queue_status},
        "audit": {
            "observability_enabled": observability["enabled"],
            "audit_file_exists": observability["audit_file_exists"],
            "immutable_audit_file_exists": audit["immutable_audit_file_exists"],
            "hash_chain_ok": audit["hash_chain_ok"],
            "total_immutable_events": audit["total_events"],
            "recent_error_events": route_health.get("recent_error_events", []),
        },
        "connectors": {
            "status": connectors["status"],
            "network_access_used": connectors["network_access_used"],
            "credentials_loaded": connectors["credentials_loaded"],
            "items": connectors["connectors"],
        },
        "campaigns": {
            "total": int(db.query(Campaign).count()),
            "by_status": campaign_status,
            "open_tickets": int(ticket_status.get("open", 0)),
            "tickets_by_status": ticket_status,
        },
        "alerts": {
            "active_blockers": active_blockers,
            "pending_human_approvals": pending_approvals,
            "open_performance_tickets": int(ticket_status.get("open", 0)),
            "queue_pending": int(queue.get("queued", 0)),
            "queue_running": int(queue.get("running", 0)),
        },
        "tasks": {
            "meta_actions_by_status": action_status,
            "pending_meta_actions": pending_approvals,
            "failed_routes": int(route_health.get("failed_routes", 0)),
        },
    }
