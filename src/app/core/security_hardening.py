from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable


class SecurityRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"
    AGENT = "AGENT"
    SERVICE = "SERVICE"


class SecurityPermission(StrEnum):
    SYSTEM_ADMIN = "system.admin"
    USER_MANAGE = "user.manage"
    CONFIG_MANAGE = "config.manage"
    AUDIT_READ = "audit.read"
    DECISION_CREATE = "decision.create"
    DECISION_READ = "decision.read"
    COMMAND_VALIDATE = "command.validate"
    APPROVAL_CREATE = "approval.create"
    APPROVAL_DECIDE = "approval.decide"
    META_READ = "meta.read"
    META_DRY_RUN = "meta.dry_run"
    META_REAL_REQUEST = "meta.real.request"
    META_REAL_EXECUTE = "meta.real.execute"
    AI_LIGHT_USE = "ai.light.use"
    AI_HEAVY_REQUEST = "ai.heavy.request"
    SITE_DRY_RUN = "site.dry_run"
    SITE_PUBLISH_REQUEST = "site.publish.request"
    INCIDENT_MANAGE = "incident.manage"


ROLE_PERMISSIONS: dict[SecurityRole, frozenset[SecurityPermission]] = {
    SecurityRole.OWNER: frozenset(SecurityPermission),
    SecurityRole.ADMIN: frozenset(
        {
            SecurityPermission.USER_MANAGE,
            SecurityPermission.CONFIG_MANAGE,
            SecurityPermission.AUDIT_READ,
            SecurityPermission.DECISION_READ,
            SecurityPermission.APPROVAL_DECIDE,
            SecurityPermission.META_READ,
            SecurityPermission.META_DRY_RUN,
            SecurityPermission.INCIDENT_MANAGE,
        }
    ),
    SecurityRole.OPERATOR: frozenset(
        {
            SecurityPermission.AUDIT_READ,
            SecurityPermission.DECISION_READ,
            SecurityPermission.COMMAND_VALIDATE,
            SecurityPermission.APPROVAL_CREATE,
            SecurityPermission.META_READ,
            SecurityPermission.META_DRY_RUN,
            SecurityPermission.META_REAL_REQUEST,
            SecurityPermission.SITE_DRY_RUN,
            SecurityPermission.SITE_PUBLISH_REQUEST,
            SecurityPermission.AI_LIGHT_USE,
            SecurityPermission.AI_HEAVY_REQUEST,
        }
    ),
    SecurityRole.VIEWER: frozenset(
        {
            SecurityPermission.AUDIT_READ,
            SecurityPermission.DECISION_READ,
            SecurityPermission.META_READ,
        }
    ),
    SecurityRole.AGENT: frozenset(
        {
            SecurityPermission.DECISION_CREATE,
            SecurityPermission.DECISION_READ,
            SecurityPermission.COMMAND_VALIDATE,
            SecurityPermission.APPROVAL_CREATE,
            SecurityPermission.META_READ,
            SecurityPermission.META_DRY_RUN,
            SecurityPermission.SITE_DRY_RUN,
            SecurityPermission.AI_LIGHT_USE,
        }
    ),
    SecurityRole.SERVICE: frozenset(
        {
            SecurityPermission.AUDIT_READ,
            SecurityPermission.COMMAND_VALIDATE,
            SecurityPermission.APPROVAL_CREATE,
            SecurityPermission.META_READ,
            SecurityPermission.META_DRY_RUN,
            SecurityPermission.SITE_DRY_RUN,
        }
    ),
}


@dataclass(frozen=True)
class SecurityActor:
    actor: str
    role: SecurityRole
    origin: str = "internal"
    scopes: frozenset[str] = field(default_factory=frozenset)

    def has_permission(self, permission: SecurityPermission | str) -> bool:
        normalized = SecurityPermission(permission)
        return normalized in ROLE_PERMISSIONS[self.role]

    def context(
        self,
        *,
        permission: SecurityPermission | str,
        correlation_id: str,
        scope: str,
    ) -> dict[str, str]:
        normalized = SecurityPermission(permission)
        return {
            "actor": self.actor,
            "role": self.role.value,
            "permission": normalized.value,
            "correlation_id": correlation_id,
            "origin": self.origin,
            "scope": scope,
        }


class PermissionDeniedError(RuntimeError):
    pass


SERVICE_ACCOUNTS: dict[str, SecurityActor] = {
    "CampaignBrain": SecurityActor("CampaignBrain", SecurityRole.AGENT, scopes=frozenset({"decision", "campaign.safe"})),
    "Brian": SecurityActor("Brian", SecurityRole.AGENT, scopes=frozenset({"learning", "decision"})),
    "MetaCampaignOperator": SecurityActor("MetaCampaignOperator", SecurityRole.SERVICE, scopes=frozenset({"meta.safe"})),
    "SiteBuilder": SecurityActor("SiteBuilder", SecurityRole.SERVICE, scopes=frozenset({"site.safe"})),
    "AuditLogger": SecurityActor("AuditLogger", SecurityRole.SERVICE, scopes=frozenset({"audit"})),
}


def service_account(name: str) -> SecurityActor:
    try:
        return SERVICE_ACCOUNTS[name]
    except KeyError as exc:
        raise PermissionDeniedError(f"Service account nao registrada: {name}") from exc


def assert_permission(actor: SecurityActor, permission: SecurityPermission | str) -> None:
    if not actor.has_permission(permission):
        raise PermissionDeniedError(f"{actor.actor} nao tem permissao {permission}.")


def allowed_permissions(role: SecurityRole | str) -> list[str]:
    normalized = SecurityRole(role)
    return sorted(permission.value for permission in ROLE_PERMISSIONS[normalized])


def can(actor: SecurityActor, permission: SecurityPermission | str) -> bool:
    return actor.has_permission(permission)


def roles_matrix() -> dict[str, list[str]]:
    return {role.value: allowed_permissions(role) for role in SecurityRole}
