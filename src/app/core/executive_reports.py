from __future__ import annotations

from typing import Any

from app.core.ad_library_search import ad_library_search_local
from app.core.enterprise_dashboard_snapshot import enterprise_dashboard_snapshot
from app.core.saas_compliance import saas_compliance_local
from app.services.campaign_brain import CampaignBrainAgent


def executive_report_local(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    blocked: list[str] = []
    if bool(payload.get("export_pdf")):
        blocked.append("pdf_export_forbidden_in_local_readiness")
    if bool(payload.get("send_email")):
        blocked.append("email_delivery_forbidden_in_local_readiness")
    if bool(payload.get("share_public_link")):
        blocked.append("public_link_forbidden_in_local_readiness")

    dashboard = enterprise_dashboard_snapshot(payload)
    compliance = saas_compliance_local(payload)
    library = ad_library_search_local(payload)
    blocked.extend(dashboard["blockers"])
    blocked.extend(compliance["blocked_reasons"])
    blocked.extend(library["blocked_reasons"])

    kpis = dashboard["kpis"]
    readiness = dashboard["readiness"]
    report_sections = [
        {
            "id": "executive_summary",
            "title": "Resumo executivo",
            "status": readiness,
            "highlights": [
                f"Global score: {kpis['global_score']}",
                f"Controles de seguranca ativos: {kpis['security_controls_active']}",
                f"Resultados preview na biblioteca: {library['results_count']}",
            ],
        },
        {
            "id": "compliance",
            "title": "Compliance",
            "status": compliance["status"],
            "highlights": compliance["frameworks"] or ["framework_pendente"],
        },
        {
            "id": "risks",
            "title": "Riscos e bloqueios",
            "status": "controlled" if not blocked else "blocked",
            "highlights": sorted(set(blocked)) or ["sem bloqueios criticos locais"],
        },
    ]
    decision = "human_review_ready" if not blocked and readiness in {"green", "yellow"} else "needs_fix_before_review"

    brain = CampaignBrainAgent()
    learning = brain.learn_after_campaign(
        {
            "product_name": "Executive Reports Local",
            "niche": payload.get("niche") or "global intelligence",
            "campaign_stage": "37W",
            "outcome": decision,
            "lesson": "Relatorio executivo deve consolidar score, compliance, riscos e biblioteca sem exportar dados para fora.",
            "metrics": {
                "sections": len(report_sections),
                "blocked_reasons": blocked,
                "readiness": readiness,
            },
        }
    )

    return {
        "mission": "37W",
        "status": "executive_report_ready" if not blocked else "blocked",
        "decision": decision,
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "database_write_used": False,
        "external_export_used": False,
        "report": {
            "title": payload.get("report_title") or "AdIntelligence Global - Executive Snapshot",
            "readiness": readiness,
            "sections": report_sections,
            "recommended_next_step": (
                "revisar com humano antes de sandbox pausado"
                if decision == "human_review_ready"
                else "corrigir bloqueios antes de apresentar para decisao"
            ),
        },
        "source_modules": {
            "dashboard": dashboard["mission"],
            "compliance": compliance["mission"],
            "ad_library_search": library["mission"],
        },
        "blocked_reasons": sorted(set(blocked)),
        "brian_learning": {
            "stored": learning["stored"],
            "message": learning["message"],
        },
    }
