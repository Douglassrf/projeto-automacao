from pathlib import Path

from app.schemas.zero_cost_stack import ZeroCostStackRequest
from app.services.zero_cost_stack import ZeroCostStackPlanner


def test_zero_cost_stack_generates_blueprint_files(monkeypatch, tmp_path):
    monkeypatch.setenv("ORCHESTRATION_OUTPUT_DIR", str(tmp_path))
    planner = ZeroCostStackPlanner()
    result = planner.build(
        ZeroCostStackRequest(
            product_name="Produto Teste",
            theme="Oferta de emagrecimento",
            llm_provider="gemini_free",
            render_provider="google_colab_comfyui",
            orchestrator="n8n_self_hosted",
            deploy_provider="github_actions_vercel",
        )
    )

    assert result.mode == "hybrid_zero_cost_no_gpu"
    assert len(result.artifacts) == 6
    assert any("GOOGLE_GEMINI_API_KEY" in warning for warning in result.warnings)
    for artifact in result.artifacts:
        assert Path(artifact.path).exists()


def test_zero_cost_master_json_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("ORCHESTRATION_OUTPUT_DIR", str(tmp_path))
    result = ZeroCostStackPlanner().build(ZeroCostStackRequest(product_name="Curso Global"))
    master = next(a for a in result.artifacts if a.name == "pipeline_master.json")
    content = Path(master.path).read_text(encoding="utf-8")
    assert "Knowledge Core JSON" in content
    assert "github_actions_vercel" in content
    assert "artifacts_expected" in content
