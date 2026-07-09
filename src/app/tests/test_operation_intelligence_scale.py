from fastapi.testclient import TestClient

from app.core.operation_intelligence_scale import (
    controlled_scale_certification,
    evidence_registry,
    feature_flag_system,
    integration_contract_testing,
    operation_intelligence_scale_plan,
    operational_runbook_system,
    policy_enforcement_engine,
    release_train_manager,
    rollback_orchestrator,
    runtime_permission_matrix,
    sandbox_execution_layer,
)
from app.main import app


def test_mission_61_release_train_manager_defines_cycles_and_freeze():
    manager = release_train_manager()

    assert manager["status"] == "release_train_ready"
    assert manager["calendar"][0]["missions"] == [61, 62, 63, 64, 65]
    assert manager["calendar"][1]["missions"] == [66, 67, 68, 69, 70]
    assert manager["freeze_rule"]["scope_lock_required"] is True


def test_mission_62_feature_flags_support_environment_and_rollback():
    flags = feature_flag_system()

    assert flags["status"] == "feature_flags_ready"
    assert set(flags["flags_by_environment"]) == {"local", "staging", "production"}
    assert flags["rollback_by_flag"] is True
    assert flags["rollout"]["steps_percent"] == [0, 10, 25, 50, 100]


def test_mission_63_sandbox_blocks_critical_action_without_authorization():
    sandbox = sandbox_execution_layer({"action": "real_meta_action"})

    assert sandbox["status"] == "blocked"
    assert sandbox["real_operations_blocked"] is True
    assert "acao_critica_exige_sandbox_ou_autorizacao" in sandbox["blocked_reasons"]


def test_mission_64_policy_enforcement_rejects_invalid_pr_rules():
    policies = policy_enforcement_engine({"merge_direct": True, "endpoint_outside_plan": True})

    assert policies["status"] == "blocked"
    assert "no_direct_merge" in policies["blocked_reasons"]
    assert "endpoints_must_be_planned" in policies["blocked_reasons"]


def test_mission_65_evidence_registry_generates_hashes_and_requires_evidence():
    evidence = evidence_registry({"files": ["a.py"], "tests": ["pytest test_a.py"]})

    assert evidence["status"] == "evidence_registry_ready"
    assert evidence["file_hashes"]["a.py"]
    assert evidence["registry_hash"]
    assert evidence["homologation_status"] == "pending_human_review"


def test_mission_66_rollback_orchestrator_blocks_untested_rollback():
    rollback = rollback_orchestrator({"rollback_tested": False})

    assert rollback["status"] == "blocked"
    assert "rollback_nao_testado" in rollback["blocked_reasons"]
    assert "post_rollback_validation" in rollback["plan"]


def test_mission_67_runtime_permission_matrix_blocks_above_permission_action():
    permissions = runtime_permission_matrix({"role": "viewer", "action": "approve_production"})

    assert permissions["status"] == "blocked"
    assert permissions["default_blocked"] is True
    assert "acao_acima_da_permissao" in permissions["blocked_reasons"]


def test_mission_68_contract_testing_detects_breaking_change():
    contracts = integration_contract_testing({"breaking_change": True})

    assert contracts["status"] == "blocked"
    assert contracts["compatibility_break_detection"] is True
    assert "quebra_de_contrato_detectada" in contracts["blocked_reasons"]


def test_mission_69_runbook_system_publishes_all_required_runbooks():
    runbooks = operational_runbook_system()

    assert runbooks["status"] == "runbooks_ready"
    assert set(runbooks["runbooks"]) == {"critical_error", "deploy", "rollback", "recovery", "audit"}


def test_mission_70_controlled_scale_certification_requires_all_controls():
    certification = controlled_scale_certification()

    assert certification["status"] == "certified_for_v1_6"
    assert all(certification["controls"].values())


def test_operation_intelligence_scale_plan_covers_missions_61_to_70():
    plan = operation_intelligence_scale_plan()

    assert plan["phase"] == "v1.5"
    assert plan["status"] == "controlled_scale_certified"
    assert plan["will_execute_real_action"] is False
    assert [item["mission"] for item in plan["mission_queue"]] == list(range(61, 71))
    assert all(plan["certification_controls"].values())
    assert set(plan["mission_deliverables"]) == {
        "mission_61_release_train",
        "mission_62_feature_flags",
        "mission_63_sandbox",
        "mission_64_policy_enforcement",
        "mission_65_evidence_registry",
        "mission_66_rollback",
        "mission_67_permissions",
        "mission_68_contracts",
        "mission_69_runbooks",
        "mission_70_certification",
    }


def test_operation_intelligence_scale_blocks_policy_violations():
    plan = operation_intelligence_scale_plan(
        {
            "mission": 99,
            "merge_direct": True,
            "production_outside_cycle": True,
            "critical_action_without_authorization": True,
        }
    )

    assert plan["status"] == "blocked"
    assert "merge_direto_bloqueado" in plan["blocked_reasons"]
    assert "missao_fora_da_fase_v1_5" in plan["blocked_reasons"]
    assert "producao_fora_do_ciclo_aprovado" in plan["blocked_reasons"]
    assert "acao_critica_sem_autorizacao" in plan["blocked_reasons"]


def test_operation_intelligence_scale_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post("/api/v1/security/operation-intelligence-scale", json={"mission": 61})

    assert response.status_code == 200
    data = response.json()
    assert data["approval_rule"] == "nenhuma missão entra em produção fora do ciclo aprovado"
    assert data["release_calendar"][0]["missions"] == [61, 62, 63, 64, 65]
