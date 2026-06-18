import pytest

from app.core.security_hardening import SecurityPermission, service_account
from app.core.zero_trust import (
    InternalCall,
    ZeroTrustError,
    ZeroTrustInternalValidator,
    make_internal_call,
)


def test_valid_internal_call_builds_auditable_envelope():
    call = make_internal_call(
        source_service="CampaignBrain",
        target_service="Brian",
        permission=SecurityPermission.DECISION_CREATE,
        scope="decision",
        correlation_id="REQ-2026-0001",
        execution_id="exec-001",
        mission_id="35D",
        payload_summary={"event": "decision.created"},
    )

    result = ZeroTrustInternalValidator().assert_valid(call)

    assert result.ok
    assert result.envelope["source"] == "CampaignBrain"
    assert result.envelope["target_service"] == "Brian"
    assert result.envelope["permission"] == "decision.create"
    assert result.envelope["correlation_id"] == "REQ-2026-0001"


def test_unknown_target_service_is_blocked():
    call = make_internal_call(
        source_service="CampaignBrain",
        target_service="UnknownService",
        permission=SecurityPermission.DECISION_CREATE,
        scope="decision",
        correlation_id="REQ-2026-0002",
    )

    result = ZeroTrustInternalValidator().validate(call)

    assert not result.ok
    assert "target_service_not_registered" in result.blocked_reasons


def test_missing_and_invalid_correlation_id_are_blocked():
    call = InternalCall(
        source=service_account("CampaignBrain"),
        target_service="Brian",
        permission=SecurityPermission.DECISION_CREATE,
        scope="decision",
        correlation_id="bad-id",
    )

    result = ZeroTrustInternalValidator().validate(call)

    assert not result.ok
    assert "correlation_id_invalid" in result.blocked_reasons


def test_scope_must_be_allowed_for_source_and_target():
    call = make_internal_call(
        source_service="CampaignBrain",
        target_service="MetaCampaignOperator",
        permission=SecurityPermission.DECISION_CREATE,
        scope="decision",
        correlation_id="REQ-2026-0003",
    )

    result = ZeroTrustInternalValidator().validate(call)

    assert not result.ok
    assert "scope_not_allowed_for_target" in result.blocked_reasons


def test_source_permission_is_enforced():
    call = make_internal_call(
        source_service="MetaCampaignOperator",
        target_service="AuditLogger",
        permission=SecurityPermission.META_REAL_EXECUTE,
        scope="meta.safe",
        correlation_id="REQ-2026-0004",
    )

    result = ZeroTrustInternalValidator().validate(call)

    assert not result.ok
    assert "source_permission_denied" in result.blocked_reasons


def test_assert_valid_raises_for_blocked_call():
    call = make_internal_call(
        source_service="SiteBuilder",
        target_service="MetaCampaignOperator",
        permission=SecurityPermission.SITE_PUBLISH_REQUEST,
        scope="site.safe",
        correlation_id="REQ-2026-0005",
    )

    with pytest.raises(ZeroTrustError):
        ZeroTrustInternalValidator().assert_valid(call)
