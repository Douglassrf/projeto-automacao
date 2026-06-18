import pytest

from app.core.human_approval import ApprovalError, ApprovalRequest, ApprovalStatus, HumanApprovalLayer
from app.core.immutable_audit import ImmutableAuditLog
from app.core.security_hardening import SecurityActor, SecurityRole, service_account


def test_agent_can_request_human_approval_with_payload_hash():
    layer = HumanApprovalLayer()
    approval = ApprovalRequest(
        action="meta.create_campaign",
        resource_type="campaign",
        resource_id="52616252576068",
        requested_by=service_account("CampaignBrain"),
        payload={"daily_budget_brl": 6, "status": "PAUSED"},
        correlation_id="REQ-2026-35F",
        reason="Campanha pausada precisa revisao humana.",
    )

    record = layer.request(approval)

    assert record.status == ApprovalStatus.PENDING
    assert record.requested_by == "CampaignBrain"
    assert len(record.payload_hash) == 64


def test_only_authorized_actor_can_approve():
    layer = HumanApprovalLayer()
    record = layer.request(
        ApprovalRequest(
            action="site.publish",
            resource_type="site",
            requested_by=service_account("SiteBuilder"),
            payload={"provider": "vercel", "dry_run": False},
            correlation_id="REQ-2026-35F-2",
        )
    )

    operator = SecurityActor("Operator", SecurityRole.OPERATOR, origin="human")
    admin = SecurityActor("Admin", SecurityRole.ADMIN, origin="human")

    with pytest.raises(Exception):
        layer.approve(record.approval_id, operator)

    approved = layer.approve(record.approval_id, admin, notes="Aprovado em revisao.")

    assert approved.status == ApprovalStatus.APPROVED
    assert approved.decided_by == "Admin"


def test_rejected_approval_cannot_be_approved_again():
    layer = HumanApprovalLayer()
    record = layer.request(
        ApprovalRequest(
            action="ai.heavy_use",
            resource_type="ai_credit",
            requested_by=SecurityActor("Operator", SecurityRole.OPERATOR, origin="human"),
            payload={"estimated_cost_usd": 10},
            correlation_id="REQ-2026-35F-3",
        )
    )
    admin = SecurityActor("Admin", SecurityRole.ADMIN, origin="human")

    rejected = layer.reject(record.approval_id, admin, notes="Custo alto.")

    assert rejected.status == ApprovalStatus.REJECTED
    with pytest.raises(ApprovalError):
        layer.approve(record.approval_id, admin)


def test_execution_requires_approved_status():
    layer = HumanApprovalLayer()
    record = layer.request(
        ApprovalRequest(
            action="meta.pause_campaign",
            resource_type="campaign",
            requested_by=SecurityActor("Operator", SecurityRole.OPERATOR, origin="human"),
            payload={"campaign_id": "52616252576068"},
            correlation_id="REQ-2026-35F-4",
        )
    )
    admin = SecurityActor("Admin", SecurityRole.ADMIN, origin="human")

    with pytest.raises(ApprovalError):
        layer.mark_executed(record.approval_id, admin)

    layer.approve(record.approval_id, admin)
    executed = layer.mark_executed(record.approval_id, admin, notes="Executado em dry-run.")

    assert executed.status == ApprovalStatus.EXECUTED


def test_approval_layer_writes_immutable_audit(tmp_path):
    audit = ImmutableAuditLog(tmp_path / "approval_immutable.jsonl")
    layer = HumanApprovalLayer(audit_log=audit)
    record = layer.request(
        ApprovalRequest(
            action="affiliate.link_change",
            resource_type="affiliate_link",
            requested_by=SecurityActor("Operator", SecurityRole.OPERATOR, origin="human"),
            payload={"old": "a", "new": "b"},
            correlation_id="REQ-2026-35F-5",
        )
    )
    admin = SecurityActor("Admin", SecurityRole.ADMIN, origin="human")

    layer.approve(record.approval_id, admin)

    verification = audit.verify()
    assert verification.ok is True
    assert verification.total_events == 2
