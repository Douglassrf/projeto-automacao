from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.models import Campaign, CampaignMetric, ContentWorkflow, DecisionLog, PerformanceTicket, QueueJob

UTC = timezone.utc

MISSION_STAGES = [
    {"id": "research_mining", "label": "Pesquisa / mineração", "source": "ad_analyses + decision_logs"},
    {"id": "strategy_intelligence", "label": "Estratégia / inteligência", "source": "campaigns + campaign_metrics"},
    {"id": "creatives", "label": "Criativos", "source": "content_workflows"},
    {"id": "site", "label": "Site", "source": "content_workflows + queue_jobs"},
    {"id": "publication", "label": "Publicação", "source": "manual gate only"},
    {"id": "monitoring", "label": "Monitoramento", "source": "performance_tickets + queue_jobs"},
]

TERMINAL_JOB_STATUSES = {"done", "dead"}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _mission_key(campaign: Campaign) -> str:
    return campaign.internal_campaign_id or f"campaign-{campaign.id}"


def _campaign_for_mission(db: Session, mission_id: str) -> Campaign | None:
    if mission_id.isdigit():
        campaign = db.get(Campaign, int(mission_id))
        if campaign:
            return campaign
    return db.query(Campaign).filter(Campaign.internal_campaign_id == mission_id).first()


def _counts(db: Session, campaign: Campaign | None = None) -> dict[str, int]:
    campaign_filter = [CampaignMetric.campaign_id == campaign.id] if campaign else []
    ticket_filter = [PerformanceTicket.campaign_id == campaign.id] if campaign else []
    return {
        "campaigns": db.query(func.count(Campaign.id)).scalar() or 0,
        "metrics": db.query(func.count(CampaignMetric.id)).filter(*campaign_filter).scalar() or 0,
        "tickets_open": db.query(func.count(PerformanceTicket.id)).filter(*ticket_filter, PerformanceTicket.status == "open").scalar() or 0,
        "tickets_total": db.query(func.count(PerformanceTicket.id)).filter(*ticket_filter).scalar() or 0,
        "queue_total": db.query(func.count(QueueJob.id)).scalar() or 0,
        "queue_active": db.query(func.count(QueueJob.id)).filter(QueueJob.status.notin_(TERMINAL_JOB_STATUSES)).scalar() or 0,
        "content_workflows": db.query(func.count(ContentWorkflow.id)).scalar() or 0,
        "decision_logs": db.query(func.count(DecisionLog.id)).scalar() or 0,
    }


def mission_plan(db: Session, mission_id: str | None = None) -> dict[str, Any]:
    campaign = _campaign_for_mission(db, mission_id) if mission_id else None
    counts = _counts(db, campaign)
    steps = []
    for index, stage in enumerate(MISSION_STAGES, start=1):
        evidence = _stage_evidence(stage["id"], counts, campaign)
        steps.append({**stage, "order": index, "status": "ready" if evidence else "waiting_for_real_data", "evidence": evidence})
    return {
        "module": "mission_planner",
        "mission_id": mission_id or (_mission_key(campaign) if campaign else None),
        "will_execute_real_action": False,
        "uses_external_integrations": False,
        "steps": steps,
    }


def _stage_evidence(stage_id: str, counts: dict[str, int], campaign: Campaign | None) -> dict[str, Any]:
    if stage_id == "research_mining":
        return {"decision_logs": counts["decision_logs"]} if counts["decision_logs"] else {}
    if stage_id == "strategy_intelligence":
        if campaign:
            return {"campaign_status": campaign.status, "metrics": counts["metrics"]}
        return {"campaigns": counts["campaigns"], "metrics": counts["metrics"]} if counts["campaigns"] or counts["metrics"] else {}
    if stage_id == "creatives":
        return {"content_workflows": counts["content_workflows"]} if counts["content_workflows"] else {}
    if stage_id == "site":
        return {"queue_total": counts["queue_total"]} if counts["queue_total"] else {}
    if stage_id == "publication":
        return {"manual_gate": "publication_requires_human_action"}
    if stage_id == "monitoring":
        return {"tickets_total": counts["tickets_total"], "queue_active": counts["queue_active"]} if counts["tickets_total"] or counts["queue_total"] else {}
    return {}


def mission_timeline(db: Session, mission_id: str) -> dict[str, Any]:
    campaign = _campaign_for_mission(db, mission_id)
    events: list[dict[str, Any]] = []
    if campaign:
        events.append({"state": "campaign_registered", "timestamp": _iso(campaign.created_at), "source": "campaigns", "detail": campaign.status})
        for metric in db.query(CampaignMetric).filter(CampaignMetric.campaign_id == campaign.id).order_by(CampaignMetric.created_at.asc()).limit(50):
            events.append({"state": "metrics_ingested", "timestamp": _iso(metric.created_at), "source": "campaign_metrics", "detail": f"roas={metric.roas}"})
        for ticket in db.query(PerformanceTicket).filter(PerformanceTicket.campaign_id == campaign.id).order_by(PerformanceTicket.created_at.asc()).limit(50):
            events.append({"state": f"ticket_{ticket.status}", "timestamp": _iso(ticket.created_at), "source": "performance_tickets", "detail": ticket.reason_code})
    return {"module": "mission_timeline", "mission_id": mission_id, "read_only": True, "events": events}


def mission_memory(db: Session, limit: int = 20) -> dict[str, Any]:
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).limit(limit).all()
    return {
        "module": "mission_memory",
        "read_only": True,
        "items": [
            {
                "mission_id": _mission_key(campaign),
                "product_name": campaign.product_name,
                "status": campaign.status,
                "created_at": _iso(campaign.created_at),
                "updated_at": _iso(campaign.updated_at),
            }
            for campaign in campaigns
        ],
    }


def mission_recovery(db: Session, mission_id: str) -> dict[str, Any]:
    timeline = mission_timeline(db, mission_id)
    completed_states = [event["state"] for event in timeline["events"]]
    next_step = next((step for step in mission_plan(db, mission_id)["steps"] if step["status"] != "ready"), None)
    return {
        "module": "mission_recovery",
        "mission_id": mission_id,
        "will_execute_real_action": False,
        "resume_policy": "skip_completed_states_and_wait_for_manual_publication_gate",
        "last_saved_state": completed_states[-1] if completed_states else None,
        "completed_states": completed_states,
        "next_step": next_step,
    }


def mission_score(db: Session, mission_id: str | None = None) -> dict[str, Any]:
    campaign = _campaign_for_mission(db, mission_id) if mission_id else None
    counts = _counts(db, campaign)
    latest_roas = 0.0
    if campaign:
        metric = db.query(CampaignMetric).filter(CampaignMetric.campaign_id == campaign.id).order_by(CampaignMetric.created_at.desc()).first()
        latest_roas = float(metric.roas) if metric else 0.0
    queue_health = 100 if counts["queue_active"] == 0 else max(0, 100 - counts["queue_active"] * 10)
    ticket_health = max(0, 100 - counts["tickets_open"] * 15)
    approval_health = 100 if counts["tickets_open"] == 0 else 70
    performance_health = min(100, int(latest_roas * 25)) if latest_roas else (60 if counts["metrics"] else 50)
    score = round((queue_health + ticket_health + approval_health + performance_health) / 4, 2)
    return {
        "module": "mission_score",
        "mission_id": mission_id,
        "score": score,
        "status": "green" if score >= 80 else "yellow" if score >= 60 else "red",
        "inputs": {**counts, "latest_roas": latest_roas},
    }


def mission_dashboard(db: Session) -> dict[str, Any]:
    memory = mission_memory(db, limit=10)
    score = mission_score(db)
    return {
        "module": "mission_dashboard",
        "layout": {"theme": "dark", "grid": ["sidebar", "content", "rightbar"]},
        "summary": score,
        "missions": memory["items"],
        "planner": mission_plan(db),
        "generated_at": datetime.now(UTC).isoformat(),
    }
