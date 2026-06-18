import pytest

from app.core.command_validator import (
    CommandAction,
    CommandGuardrails,
    CommandValidationError,
    CommandValidator,
    SensitiveCommand,
)
from app.core.security_hardening import SecurityActor, SecurityRole, service_account


def test_dry_run_command_from_agent_is_allowed():
    command = SensitiveCommand(
        action=CommandAction.DRY_RUN,
        actor=service_account("CampaignBrain"),
        platform="local",
        objective="DRY_RUN",
        dry_run=True,
        correlation_id="REQ-2026-0001",
    )

    result = CommandValidator().validate(command)

    assert result.ok
    assert result.blocked_reasons == ()
    assert result.command_context["actor"] == "CampaignBrain"
    assert result.command_context["permission"] == "command.validate"


def test_agent_cannot_request_real_meta_campaign():
    command = SensitiveCommand(
        action=CommandAction.META_CREATE_CAMPAIGN,
        actor=service_account("CampaignBrain"),
        platform="meta",
        objective="OUTCOME_SALES",
        countries=("BR",),
        daily_budget_brl=6,
        dry_run=False,
        human_approved=True,
    )

    result = CommandValidator().validate(command)

    assert not result.ok
    assert "actor_permission_denied" in result.blocked_reasons


def test_operator_real_meta_request_requires_human_approval():
    operator = SecurityActor("DouglasOperator", SecurityRole.OPERATOR, origin="human")
    command = SensitiveCommand(
        action=CommandAction.META_CREATE_CAMPAIGN,
        actor=operator,
        platform="meta",
        objective="OUTCOME_SALES",
        countries=("BR",),
        daily_budget_brl=6,
        dry_run=False,
        human_approved=False,
    )

    result = CommandValidator().validate(command)

    assert not result.ok
    assert result.requires_human_approval is True
    assert "human_approval_required" in result.blocked_reasons


def test_operator_real_meta_request_within_limits_and_approval_is_allowed():
    operator = SecurityActor("DouglasOperator", SecurityRole.OPERATOR, origin="human")
    command = SensitiveCommand(
        action=CommandAction.META_CREATE_CAMPAIGN,
        actor=operator,
        platform="meta",
        objective="OUTCOME_SALES",
        countries=("BR",),
        daily_budget_brl=6,
        dry_run=False,
        human_approved=True,
        resource_id="52616252576068",
    )

    result = CommandValidator().assert_valid(command)

    assert result.ok
    assert result.requires_human_approval is True


def test_budget_country_platform_objective_and_resource_are_blocked():
    operator = SecurityActor("DouglasOperator", SecurityRole.OPERATOR, origin="human")
    command = SensitiveCommand(
        action=CommandAction.META_UPDATE_BUDGET,
        actor=operator,
        platform="unknown",
        objective="AWARENESS",
        countries=("ZZ",),
        daily_budget_brl=500,
        resource_id="unsafe-resource",
        dry_run=False,
        human_approved=True,
    )

    result = CommandValidator(CommandGuardrails(max_daily_budget_brl=50)).validate(command)

    assert set(result.blocked_reasons) == {
        "platform_not_allowed",
        "objective_not_allowed",
        "country_not_allowed",
        "budget_above_limit",
        "resource_id_not_allowed",
    }


def test_assert_valid_raises_when_command_is_blocked():
    viewer = SecurityActor("Viewer", SecurityRole.VIEWER, origin="human")
    command = SensitiveCommand(
        action=CommandAction.AI_HEAVY_USE,
        actor=viewer,
        platform="ai",
        objective="DRY_RUN",
        dry_run=False,
        human_approved=False,
    )

    with pytest.raises(CommandValidationError):
        CommandValidator().assert_valid(command)
