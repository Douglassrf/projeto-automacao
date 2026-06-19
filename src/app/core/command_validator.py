from __future__ import annotations

from dataclasses import dataclass, field
try:
    from enum import StrEnum
except ImportError:  # compat Python 3.10 (StrEnum requer 3.11+)
    from enum import Enum

    class StrEnum(str, Enum):
        pass
from typing import Any

from app.core.security_hardening import (
    SecurityActor,
    SecurityPermission,
    assert_permission,
)


class CommandAction(StrEnum):
    META_CREATE_CAMPAIGN = "meta.create_campaign"
    META_UPDATE_BUDGET = "meta.update_budget"
    META_PAUSE_CAMPAIGN = "meta.pause_campaign"
    SITE_PUBLISH = "site.publish"
    AFFILIATE_LINK_CHANGE = "affiliate.link_change"
    AI_HEAVY_USE = "ai.heavy_use"
    DRY_RUN = "dry_run"


class CommandValidationStatus(StrEnum):
    OK = "ok"
    BLOCKED = "blocked"


class CommandValidationError(RuntimeError):
    pass


ACTION_PERMISSIONS: dict[CommandAction, SecurityPermission] = {
    CommandAction.META_CREATE_CAMPAIGN: SecurityPermission.META_REAL_REQUEST,
    CommandAction.META_UPDATE_BUDGET: SecurityPermission.META_REAL_REQUEST,
    CommandAction.META_PAUSE_CAMPAIGN: SecurityPermission.META_REAL_REQUEST,
    CommandAction.SITE_PUBLISH: SecurityPermission.SITE_PUBLISH_REQUEST,
    CommandAction.AFFILIATE_LINK_CHANGE: SecurityPermission.APPROVAL_CREATE,
    CommandAction.AI_HEAVY_USE: SecurityPermission.AI_HEAVY_REQUEST,
    CommandAction.DRY_RUN: SecurityPermission.COMMAND_VALIDATE,
}


REAL_ACTIONS_REQUIRING_APPROVAL = {
    CommandAction.META_CREATE_CAMPAIGN,
    CommandAction.META_UPDATE_BUDGET,
    CommandAction.META_PAUSE_CAMPAIGN,
    CommandAction.SITE_PUBLISH,
    CommandAction.AFFILIATE_LINK_CHANGE,
    CommandAction.AI_HEAVY_USE,
}


@dataclass(frozen=True)
class CommandGuardrails:
    max_daily_budget_brl: float = 50.0
    allowed_countries: frozenset[str] = frozenset({"BR", "AR", "CL", "CO", "PE", "MX", "EC", "US", "PT", "ES"})
    allowed_platforms: frozenset[str] = frozenset({"meta", "facebook", "instagram", "site", "local", "ai"})
    allowed_objectives: frozenset[str] = frozenset({"OUTCOME_SALES", "PURCHASE", "LEAD", "TRAFFIC", "DRY_RUN"})
    allowed_resource_prefixes: frozenset[str] = frozenset({"act_", "cmp_", "dry_", "site_", "ai_", "526"})


@dataclass(frozen=True)
class SensitiveCommand:
    action: CommandAction
    actor: SecurityActor
    platform: str
    objective: str = "DRY_RUN"
    countries: tuple[str, ...] = ()
    resource_id: str | None = None
    daily_budget_brl: float = 0.0
    dry_run: bool = True
    human_approved: bool = False
    correlation_id: str = "REQ-LOCAL-SAFE"
    scope: str = "command.safe"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandValidationResult:
    status: CommandValidationStatus
    blocked_reasons: tuple[str, ...]
    command_context: dict[str, str]
    requires_human_approval: bool

    @property
    def ok(self) -> bool:
        return self.status == CommandValidationStatus.OK


class CommandValidator:
    def __init__(self, guardrails: CommandGuardrails | None = None) -> None:
        self.guardrails = guardrails or CommandGuardrails()

    def validate(self, command: SensitiveCommand) -> CommandValidationResult:
        blocked: list[str] = []
        required_permission = ACTION_PERMISSIONS[command.action]

        try:
            assert_permission(command.actor, required_permission)
        except Exception:
            blocked.append("actor_permission_denied")

        platform = command.platform.strip().lower()
        if platform not in self.guardrails.allowed_platforms:
            blocked.append("platform_not_allowed")

        objective = command.objective.strip().upper()
        if objective not in self.guardrails.allowed_objectives:
            blocked.append("objective_not_allowed")

        countries = tuple(country.strip().upper() for country in command.countries if country.strip())
        if any(country not in self.guardrails.allowed_countries for country in countries):
            blocked.append("country_not_allowed")

        if command.daily_budget_brl < 0:
            blocked.append("budget_negative")
        if command.daily_budget_brl > self.guardrails.max_daily_budget_brl:
            blocked.append("budget_above_limit")

        if command.resource_id and not self._resource_id_allowed(command.resource_id):
            blocked.append("resource_id_not_allowed")

        requires_approval = command.action in REAL_ACTIONS_REQUIRING_APPROVAL and not command.dry_run
        if requires_approval and not command.human_approved:
            blocked.append("human_approval_required")

        context = command.actor.context(
            permission=required_permission,
            correlation_id=command.correlation_id,
            scope=command.scope,
        )
        status = CommandValidationStatus.BLOCKED if blocked else CommandValidationStatus.OK
        return CommandValidationResult(
            status=status,
            blocked_reasons=tuple(blocked),
            command_context=context,
            requires_human_approval=requires_approval,
        )

    def assert_valid(self, command: SensitiveCommand) -> CommandValidationResult:
        result = self.validate(command)
        if not result.ok:
            raise CommandValidationError(", ".join(result.blocked_reasons))
        return result

    def _resource_id_allowed(self, resource_id: str) -> bool:
        normalized = resource_id.strip()
        return any(normalized.startswith(prefix) for prefix in self.guardrails.allowed_resource_prefixes)

