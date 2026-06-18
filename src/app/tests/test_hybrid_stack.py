from app.services.hybrid_stack import HybridNoGpuStackPlanner
from app.schemas.hybrid_stack import HybridStackRequest


def test_hybrid_stack_plan_generates_artifacts():
    response = HybridNoGpuStackPlanner().build_plan(
        HybridStackRequest(
            product_name="Produto Teste Sem GPU",
            goal="Validar pipeline híbrido",
            media_provider="colab_comfyui",
            llm_provider="ollama_cpu",
            deploy_target="vercel",
        )
    )

    assert response.architecture_mode == "hybrid_local_plus_free_cloud"
    assert response.estimated_fixed_cost.startswith("R$0")
    assert response.plan_file.endswith("hybrid_no_gpu_plan.json")
    assert response.github_actions_file.endswith("github_actions_ci.yml")
    assert response.rag_manifest_file.endswith("rag_manifest.json")
    assert len(response.steps) == 6
    assert any(step.layer == "RAG" for step in response.steps)
