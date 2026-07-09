from __future__ import annotations

from datetime import date
from hashlib import sha256
from typing import Any

PHASE = "v1.5"
PHASE_NAME = "Operacao Inteligente e Escala Controlada"
MISSIONS = tuple(range(61, 71))
FREEZE_DAYS_BEFORE_MERGE = 2
ENVIRONMENTS = ("local", "staging", "production")
CRITICAL_ACTIONS = {"deploy_production", "spend_money", "real_meta_action", "delete_data", "rollback_release"}


def _blocked_reasons(payload: dict[str, Any]) -> list[str]:
    blocked: list[str] = []
    requested_mission = payload.get("mission")
    if payload.get("merge_direct") is True:
        blocked.append("merge_direto_bloqueado")
    if payload.get("production_outside_cycle") is True:
        blocked.append("producao_fora_do_ciclo_aprovado")
    if payload.get("critical_action_without_authorization") is True:
        blocked.append("acao_critica_sem_autorizacao")
    if requested_mission is not None and requested_mission not in MISSIONS:
        blocked.append("missao_fora_da_fase_v1_5")
    return sorted(set(blocked))


def release_train_manager(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    calendar = [
        {
            "version": "v1.5.0",
            "cycle": "RT-2026-07-A",
            "status": "planned",
            "scope": "governanca operacional e controles de release",
            "missions": [61, 62, 63, 64, 65],
            "freeze_rule": f"congelamento obrigatório {FREEZE_DAYS_BEFORE_MERGE} dias antes do merge aprovado",
        },
        {
            "version": "v1.5.1",
            "cycle": "RT-2026-07-B",
            "status": "planned",
            "scope": "resiliência, permissões, contratos e runbooks",
            "missions": [66, 67, 68, 69, 70],
            "freeze_rule": f"congelamento obrigatório {FREEZE_DAYS_BEFORE_MERGE} dias antes do merge aprovado",
        },
    ]
    mission_queue = [
        {"mission": 61, "name": "Release Train Manager", "version": "v1.5.0", "order": 1},
        {"mission": 62, "name": "Feature Flag System", "version": "v1.5.0", "order": 2},
        {"mission": 63, "name": "Sandbox Execution Layer", "version": "v1.5.0", "order": 3},
        {"mission": 64, "name": "Policy Enforcement Engine", "version": "v1.5.0", "order": 4},
        {"mission": 65, "name": "Evidence Registry", "version": "v1.5.0", "order": 5},
        {"mission": 66, "name": "Rollback Orchestrator", "version": "v1.5.1", "order": 6},
        {"mission": 67, "name": "Runtime Permission Matrix", "version": "v1.5.1", "order": 7},
        {"mission": 68, "name": "Integration Contract Testing", "version": "v1.5.1", "order": 8},
        {"mission": 69, "name": "Operational Runbook System", "version": "v1.5.1", "order": 9},
        {"mission": 70, "name": "Controlled Scale Certification", "version": "v1.5.1", "order": 10},
    ]
    blocked = []
    if payload.get("production_outside_cycle") is True:
        blocked.append("release_train_rejeitou_producao_fora_do_ciclo")
    return {
        "mission": 61,
        "status": "blocked" if blocked else "release_train_ready",
        "calendar": calendar,
        "mission_queue": mission_queue,
        "freeze_rule": {"days_before_merge": FREEZE_DAYS_BEFORE_MERGE, "scope_lock_required": True},
        "mandatory_checklist": ["escopo aprovado", "testes verdes", "evidências registradas", "rollback definido"],
        "approval_rule": "nenhuma missão entra em produção fora do ciclo aprovado",
        "blocked_reasons": blocked,
    }


def feature_flag_system(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    flags = {
        env: {
            "release_train_manager": True,
            "sandbox_execution": env != "production",
            "policy_enforcement": True,
            "evidence_registry": True,
            "rollback_orchestrator": env != "local",
            "controlled_scale": False,
        }
        for env in ENVIRONMENTS
    }
    rollout = {"strategy": "gradual", "steps_percent": [0, 10, 25, 50, 100], "requires_evidence_each_step": True}
    history = [{"flag": "policy_enforcement", "environment": "all", "from": False, "to": True, "reason": "v1.5 baseline"}]
    blocked = []
    if payload.get("new_function_without_flag") is True:
        blocked.append("funcao_nova_sem_feature_flag")
    return {
        "mission": 62,
        "status": "blocked" if blocked else "feature_flags_ready",
        "flags_by_environment": flags,
        "rollout": rollout,
        "rollback_by_flag": True,
        "change_history": history,
        "approval_rule": "toda função nova pode ser desligada sem mexer no código",
        "blocked_reasons": blocked,
    }


def sandbox_execution_layer(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    critical_action = payload.get("action") in CRITICAL_ACTIONS
    authorized = payload.get("authorized") is True
    blocked = []
    if critical_action and not authorized:
        blocked.append("acao_critica_exige_sandbox_ou_autorizacao")
    return {
        "mission": 63,
        "status": "blocked" if blocked else "sandbox_ready",
        "isolated_environment": True,
        "temporary_database": "sqlite:///:memory:",
        "campaign_simulation_only": True,
        "real_operations_blocked": True,
        "approval_rule": "nenhuma ação crítica roda fora do sandbox sem autorização",
        "blocked_reasons": blocked,
    }


def policy_enforcement_engine(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    policies = {
        "no_direct_merge": payload.get("merge_direct") is not True,
        "mission_requires_scope": bool(payload.get("scope", "escopo_v1_5")),
        "endpoints_must_be_planned": payload.get("endpoint_outside_plan") is not True,
        "pre_pr_validation_required": True,
    }
    blocked = [name for name, passed in policies.items() if not passed]
    return {
        "mission": 64,
        "status": "blocked" if blocked else "policy_enforcement_ready",
        "policies": policies,
        "approval_rule": "PR fora das regras é reprovado automaticamente",
        "blocked_reasons": blocked,
    }


def evidence_registry(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    files = payload.get("files") or ["src/app/core/operation_intelligence_scale.py"]
    tests = payload.get("tests") or ["pytest src/app/tests/test_operation_intelligence_scale.py"]
    evidence_text = "|".join([*files, *tests, PHASE])
    blocked = []
    if payload.get("missing_evidence") is True:
        blocked.append("missao_sem_evidencia")
    return {
        "mission": 65,
        "status": "blocked" if blocked else "evidence_registry_ready",
        "test_records": tests,
        "execution_logs": payload.get("logs") or ["local pytest passed"],
        "file_hashes": {file_name: sha256(file_name.encode()).hexdigest() for file_name in files},
        "pr_links": payload.get("pr_links") or [],
        "homologation_status": "pending_human_review",
        "registry_hash": sha256(evidence_text.encode()).hexdigest(),
        "approval_rule": "nenhuma missão é aprovada sem evidência",
        "blocked_reasons": blocked,
    }


def rollback_orchestrator(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    plan = {
        "by_release": ["reverter tag da versão", "restaurar flags anteriores", "validar smoke test"],
        "by_module": ["desativar feature flag", "reverter módulo afetado", "rodar contrato do módulo"],
        "automatic_reversal": ["pausar rollout", "restaurar configuração segura", "notificar auditoria"],
        "post_rollback_validation": ["health check", "contratos", "evidências"],
    }
    blocked = [] if payload.get("rollback_tested", True) else ["rollback_nao_testado"]
    return {
        "mission": 66,
        "status": "blocked" if blocked else "rollback_orchestrator_ready",
        "plan": plan,
        "approval_rule": "rollback testado e documentado",
        "blocked_reasons": blocked,
    }


def runtime_permission_matrix(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    matrix = {
        "viewer": {"risk_level": 0, "allowed_actions": ["read_status", "read_runbook"]},
        "operator": {"risk_level": 1, "allowed_actions": ["run_tests", "simulate_campaign", "toggle_staging_flag"]},
        "release_manager": {"risk_level": 2, "allowed_actions": ["approve_cycle", "request_rollback", "freeze_release"]},
        "human_owner": {"risk_level": 3, "allowed_actions": ["approve_production", "approve_critical_action"]},
    }
    role = payload.get("role", "operator")
    action = payload.get("action", "simulate_campaign")
    allowed = action in matrix.get(role, {}).get("allowed_actions", [])
    critical = action in CRITICAL_ACTIONS
    extra_confirmation = critical or matrix.get(role, {}).get("risk_level", 0) >= 2
    blocked = []
    if not allowed and action != "simulate_campaign":
        blocked.append("acao_acima_da_permissao")
    if critical and payload.get("confirmed") is not True:
        blocked.append("acao_critica_exige_confirmacao_extra")
    return {
        "mission": 67,
        "status": "blocked" if blocked else "runtime_permissions_ready",
        "permission_matrix": matrix,
        "default_blocked": True,
        "extra_confirmation_required": extra_confirmation,
        "approval_rule": "nenhum agente executa ação acima da própria permissão",
        "blocked_reasons": blocked,
    }


def integration_contract_testing(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    contracts = [
        {"provider": "security_api", "consumer": "release_train", "input": "policy payload", "output": "blocked_reasons"},
        {"provider": "feature_flags", "consumer": "rollback", "input": "flag name", "output": "safe toggle result"},
        {"provider": "evidence_registry", "consumer": "certification", "input": "mission id", "output": "evidence hash"},
    ]
    blocked = []
    if payload.get("breaking_change") is True:
        blocked.append("quebra_de_contrato_detectada")
    return {
        "mission": 68,
        "status": "blocked" if blocked else "contract_testing_ready",
        "contracts": contracts,
        "io_tests_required": True,
        "internal_api_validation": True,
        "compatibility_break_detection": True,
        "approval_rule": "mudança incompatível bloqueia o PR",
        "blocked_reasons": blocked,
    }


def operational_runbook_system(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    runbooks = {
        "critical_error": ["parar rollout", "coletar evidência", "acionar owner humano"],
        "deploy": ["validar ciclo", "checar freeze", "executar smoke test", "registrar evidência"],
        "rollback": ["acionar orquestrador", "desativar flag", "validar pós-rollback"],
        "recovery": ["restaurar estado seguro", "reprocessar fila", "auditar impacto"],
        "audit": ["coletar logs", "validar hashes", "anexar status de homologação"],
    }
    return {
        "mission": 69,
        "status": "runbooks_ready",
        "runbooks": runbooks,
        "approval_rule": "qualquer agente consegue seguir o procedimento sem improvisar",
        "blocked_reasons": [],
    }


def controlled_scale_certification(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    controls = {
        "release_train": release_train_manager(payload)["status"] != "blocked",
        "feature_flags": feature_flag_system(payload)["status"] != "blocked",
        "sandbox": sandbox_execution_layer(payload)["status"] != "blocked",
        "policies": policy_enforcement_engine(payload)["status"] != "blocked",
        "evidence": evidence_registry(payload)["status"] != "blocked",
        "rollback": rollback_orchestrator(payload)["status"] != "blocked",
        "permissions": runtime_permission_matrix(payload)["status"] != "blocked",
        "contracts": integration_contract_testing(payload)["status"] != "blocked",
        "runbooks": operational_runbook_system(payload)["status"] != "blocked",
        "governance": not _blocked_reasons(payload),
    }
    blocked = [name for name, passed in controls.items() if not passed]
    return {
        "mission": 70,
        "status": "certified_for_v1_6" if not blocked else "blocked",
        "controls": controls,
        "approval_rule": "sistema apto para evolução v1.6 sem perder controle",
        "blocked_reasons": blocked,
    }


def operation_intelligence_scale_plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    missions = {
        "mission_61_release_train": release_train_manager(payload),
        "mission_62_feature_flags": feature_flag_system(payload),
        "mission_63_sandbox": sandbox_execution_layer(payload),
        "mission_64_policy_enforcement": policy_enforcement_engine(payload),
        "mission_65_evidence_registry": evidence_registry(payload),
        "mission_66_rollback": rollback_orchestrator(payload),
        "mission_67_permissions": runtime_permission_matrix(payload),
        "mission_68_contracts": integration_contract_testing(payload),
        "mission_69_runbooks": operational_runbook_system(payload),
        "mission_70_certification": controlled_scale_certification(payload),
    }
    blocked = _blocked_reasons(payload)
    for mission in missions.values():
        blocked.extend(mission["blocked_reasons"])
    blocked = sorted(set(blocked))
    release_train = missions["mission_61_release_train"]
    certification = missions["mission_70_certification"]
    return {
        "phase": PHASE,
        "phase_name": PHASE_NAME,
        "status": "controlled_scale_certified" if not blocked else "blocked",
        "generated_at": date.today().isoformat(),
        "will_execute_real_action": False,
        "will_activate_spend": False,
        "network_access_used": False,
        "release_calendar": release_train["calendar"],
        "mission_queue": release_train["mission_queue"],
        "freeze_rule": release_train["freeze_rule"],
        "mandatory_release_checklist": release_train["mandatory_checklist"],
        "certification_controls": certification["controls"],
        "mission_deliverables": missions,
        "approval_rule": "nenhuma missão entra em produção fora do ciclo aprovado",
        "blocked_reasons": blocked,
    }
