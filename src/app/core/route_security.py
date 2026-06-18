from __future__ import annotations

from typing import Any

from app.core.command_validator import CommandAction, CommandValidator, SensitiveCommand
from app.core.security_hardening import SecurityActor, SecurityRole


API_OPERATOR_ACTOR = SecurityActor(
    actor="ApiOperator",
    role=SecurityRole.OPERATOR,
    origin="api",
    scopes=frozenset({"meta.safe", "production.review", "site.safe", "ai.safe", "affiliate.safe"}),
)


def meta_production_security_guard(payload: dict[str, Any], *, correlation_id: str = "REQ-API-GUARD") -> dict[str, Any]:
    launch_payload = payload.get("launch_payload") if isinstance(payload.get("launch_payload"), dict) else payload
    daily_budget = float(launch_payload.get("daily_budget_brl") or launch_payload.get("budget_brl") or 0)
    human_approved = all(
        bool(payload.get(key))
        for key in ("confirmed_by_user", "rollback_policy_ack", "brain_approval_ack")
    )
    result = CommandValidator().validate(
        SensitiveCommand(
            action=CommandAction.META_CREATE_CAMPAIGN,
            actor=API_OPERATOR_ACTOR,
            platform="meta",
            objective=str(launch_payload.get("objective") or "OUTCOME_SALES"),
            countries=("BR",),
            resource_id=str(launch_payload.get("campaign_id")) if launch_payload.get("campaign_id") else None,
            daily_budget_brl=daily_budget,
            dry_run=bool(payload.get("force_dry_run", False)),
            human_approved=human_approved,
            correlation_id=correlation_id,
            scope="meta.production.request",
        )
    )
    return {
        "status": result.status.value,
        "blocked_reasons": list(result.blocked_reasons),
        "requires_human_approval": result.requires_human_approval,
        "command_context": result.command_context,
    }


def site_publish_security_guard(payload: dict[str, Any], *, correlation_id: str = "REQ-SITE-GUARD") -> dict[str, Any]:
    deploy = payload.get("deploy") if isinstance(payload.get("deploy"), dict) else {}
    dry_run = bool(deploy.get("dry_run", True))
    result = CommandValidator().validate(
        SensitiveCommand(
            action=CommandAction.SITE_PUBLISH,
            actor=API_OPERATOR_ACTOR,
            platform="site",
            objective="DRY_RUN",
            dry_run=dry_run,
            human_approved=bool(payload.get("confirmed_by_user")),
            correlation_id=correlation_id,
            scope="site.publish.request",
        )
    )
    return _guard_response(result)


def ai_heavy_security_guard(payload: dict[str, Any], *, correlation_id: str = "REQ-AI-GUARD") -> dict[str, Any]:
    provider = str(payload.get("provider") or payload.get("scene_provider") or "local")
    dry_run = bool(payload.get("dry_run", provider in {"dry_run", "local", "ffmpeg_local", "fallback"}))
    result = CommandValidator().validate(
        SensitiveCommand(
            action=CommandAction.AI_HEAVY_USE,
            actor=API_OPERATOR_ACTOR,
            platform="ai",
            objective="DRY_RUN",
            resource_id=f"ai_{provider}",
            dry_run=dry_run,
            human_approved=bool(payload.get("confirmed_by_user")),
            correlation_id=correlation_id,
            scope="ai.heavy.request",
        )
    )
    return _guard_response(result)


def affiliate_link_security_guard(payload: dict[str, Any], *, correlation_id: str = "REQ-AFFILIATE-GUARD") -> dict[str, Any]:
    result = CommandValidator().validate(
        SensitiveCommand(
            action=CommandAction.AFFILIATE_LINK_CHANGE,
            actor=API_OPERATOR_ACTOR,
            platform="local",
            objective="DRY_RUN",
            resource_id=f"dry_affiliate_{payload.get('ad_id') or 'local'}",
            dry_run=True,
            human_approved=True,
            correlation_id=correlation_id,
            scope="affiliate.link_change",
        )
    )
    return _guard_response(result)


def _guard_response(result: Any) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "blocked_reasons": list(result.blocked_reasons),
        "requires_human_approval": result.requires_human_approval,
        "command_context": result.command_context,
    }


def with_security_guard(response: dict[str, Any], guard: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(response)
    enriched["security_guard"] = guard
    return enriched
