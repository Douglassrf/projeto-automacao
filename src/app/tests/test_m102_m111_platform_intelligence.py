from app.services.platform_intelligence_service import PlatformIntelligenceService


def test_platform_intelligence_manages_missions_102_to_111():
    snapshot = PlatformIntelligenceService().platform_snapshot()

    mission_ids = {
        mission["id"] for mission in snapshot["mission_orchestrator"]["missions"]
    }

    assert snapshot["phase"] == "v1.9"
    assert mission_ids == {str(number) for number in range(102, 112)}
    assert all(
        mission["state"] == "managed"
        for mission in snapshot["mission_orchestrator"]["missions"]
    )
    assert snapshot["decision_center"]
    assert snapshot["risk_engine"]["risks"]
    assert snapshot["architecture_knowledge_graph"]["searchable"] is True
    assert "release_governance" in snapshot


def test_platform_intelligence_tracks_git_pr_ci_governance():
    snapshot = PlatformIntelligenceService().platform_snapshot()
    release_governance = snapshot["release_governance"]

    assert release_governance["current_branch"]
    assert release_governance["homologation_pr_status"] in {
        "ready",
        "requires_remote_configuration",
    }
    assert release_governance["ci_validation_status"] in {
        "workflows_detected",
        "blocked_no_workflows",
    }
    assert "git_pr_ci" in snapshot["enterprise_audit"]["validated_domains"]
