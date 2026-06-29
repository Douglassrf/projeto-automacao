from pathlib import Path

from app.services.engineering_control_tower_service import EngineeringControlTowerService


def test_control_tower_snapshot_covers_missions_without_db():
    snapshot = EngineeringControlTowerService(db=None).snapshot()

    assert snapshot["overall_status"] in {"healthy", "attention"}
    assert snapshot["global_status"]["modules"]["services"] > 0
    assert "branches" in snapshot["global_status"]
    assert "pull_requests" in snapshot["global_status"]
    assert "tests" in snapshot["global_status"]
    assert "pipelines" in snapshot["global_status"]
    assert "teams" in snapshot["global_status"]
    assert "refactoring" in snapshot
    assert "dependency_health" in snapshot
    assert "architecture_consistency" in snapshot
    assert "documentation_manager" in snapshot
    assert "operational_advisor" in snapshot
    assert "simulation_center" in snapshot
    assert "long_term_stability" in snapshot
    assert "enterprise_operations" in snapshot
    assert "legacy_evolution_certification" in snapshot


def test_refactoring_report_prioritizes_static_findings(tmp_path: Path):
    app = tmp_path / "src" / "app"
    services = app / "services"
    services.mkdir(parents=True)
    sample = services / "sample_service.py"
    sample.write_text(
        "class Big:\n"
        + "\n".join(f"    def m{i}(self):\n        return {i}" for i in range(13))
        + "\n\ndef repeated():\n    return 1\n\ndef repeated():\n    return 1\n",
        encoding="utf-8",
    )

    report = EngineeringControlTowerService(root=tmp_path).refactoring_report()

    assert report["complex_classes"]
    assert report["duplicated_code"]
    assert report["prioritized_suggestions"]


def test_control_tower_markdown_has_single_screen_summary():
    markdown = EngineeringControlTowerService(db=None).render_markdown()

    assert "Engineering Control Tower" in markdown
    assert "Saúde global" in markdown
    assert "Recomendações priorizadas" in markdown
    assert "PR homologação" in markdown
    assert "CI remoto" in markdown
