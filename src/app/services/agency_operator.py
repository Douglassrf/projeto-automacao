from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4
from sqlalchemy.orm import Session

from app.domain.models import ContentWorkflow
from app.schemas.agency_operator import AgencyWorkflowCreateRequest


def _draft_from_request(payload: AgencyWorkflowCreateRequest) -> dict:
    hook = payload.brief.strip().split(".")[0][:140]
    return {
        "headline": payload.title,
        "hook": hook,
        "body": payload.brief,
        "cta": "Aprovar e publicar" if payload.content_type != "reply" else "Responder com segurança",
        "channel": payload.platform,
        "content_type": payload.content_type,
        "guardrails": [
            "não publicar sem aprovação humana quando requires_approval=true",
            "não expor tokens no frontend",
            "registrar cada transição de estado",
        ],
    }


def _to_response(item: ContentWorkflow) -> dict:
    try:
        draft = json.loads(item.draft_json or "{}")
    except json.JSONDecodeError:
        draft = {}
    return {
        "id": item.id,
        "workflow_key": item.workflow_key,
        "title": item.title,
        "platform": item.platform,
        "content_type": item.content_type,
        "status": item.status,
        "draft": draft,
        "approval_notes": item.approval_notes,
        "failure_reason": item.failure_reason,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


class AgencyOperatorService:
    def __init__(self, db: Session):
        self.db = db

    def create_workflow(self, payload: AgencyWorkflowCreateRequest) -> dict:
        status = "REVIEW_PENDING" if payload.requires_approval else "CREATED"
        item = ContentWorkflow(
            workflow_key=f"agency_{uuid4().hex[:12]}",
            title=payload.title,
            platform=payload.platform,
            content_type=payload.content_type,
            status=status,
            draft_json=json.dumps(_draft_from_request(payload), ensure_ascii=False),
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return _to_response(item)

    def list_workflows(self, limit: int = 20) -> dict:
        items = (
            self.db.query(ContentWorkflow)
            .order_by(ContentWorkflow.updated_at.desc())
            .limit(limit)
            .all()
        )
        return {"total": len(items), "items": [_to_response(item) for item in items]}

    def transition(self, workflow_id: int, action: str, notes: str = "") -> dict:
        item = self.db.get(ContentWorkflow, workflow_id)
        if not item:
            raise ValueError("Workflow não encontrado")

        transitions = {
            "approve": "APPROVED",
            "schedule": "SCHEDULED",
            "publish": "PUBLISHED",
            "fail": "FAILED",
            "retry": "RETRYING",
        }
        if action not in transitions:
            raise ValueError("Ação inválida")

        item.status = transitions[action]
        item.approval_notes = notes or item.approval_notes
        if action == "fail":
            item.failure_reason = notes or "Falha registrada manualmente"
        item.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(item)
        return _to_response(item)
