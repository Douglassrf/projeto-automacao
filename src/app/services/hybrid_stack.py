from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings, safe_project_path
from app.services.knowledge_engine import KnowledgeEngine
from app.schemas.hybrid_stack import HybridStackRequest, HybridStackResponse, HybridStackStep


def _safe_slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or f"hybrid-{uuid4().hex[:8]}"


class HybridNoGpuStackPlanner:
    """Planeja a arquitetura híbrida local+nuvem para operar sem GPU própria.

    O serviço não tenta renderizar IA pesada localmente. Ele gera os artefatos de
    execução: plano JSON, manifesto RAG, workflow GitHub Actions e Dockerfile de
    referência para Cloud Run/serverless.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.output_root = safe_project_path(self.settings.orchestration_output_dir, "data/orchestration_runs") / "hybrid_stack"
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.knowledge = KnowledgeEngine()

    def build_plan(self, payload: HybridStackRequest) -> HybridStackResponse:
        generated_at = datetime.now(timezone.utc)
        slug = _safe_slug(payload.product_name)
        output_dir = self.output_root / slug / generated_at.strftime("%Y%m%d-%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)

        rules = self.knowledge.load("hybrid_stack_rules")
        warnings: list[str] = []
        steps = self._build_steps(payload)

        if payload.has_gpu:
            warnings.append("GPU marcada como disponível, mas o plano mantém fallback híbrido para evitar custo fixo.")
        if payload.deploy_target == "aws_lambda":
            warnings.append("AWS Lambda exige adaptação ASGI/Mangum para FastAPI em produção.")
        if payload.media_provider in {"colab_comfyui", "huggingface_spaces"}:
            warnings.append("Render IA externo deve permanecer assíncrono/dry-run até validar credenciais e limites gratuitos.")

        plan = {
            "schema_version": "1.0",
            "generated_at": generated_at.isoformat(),
            "product_name": payload.product_name,
            "goal": payload.goal,
            "architecture": {
                "backend": "FastAPI stateless",
                "frontend": "React/Vite static",
                "media_heavy_jobs": payload.media_provider,
                "llm_learning": payload.llm_provider,
                "deploy_target": payload.deploy_target,
                "build_runner": "GitHub Actions" if payload.use_github_actions else "local npm/pytest",
                "fixed_cost": "R$0 previsto em baixo volume/free tier",
            },
            "knowledge_rules": rules,
            "steps": [step.model_dump(mode="json") for step in steps],
            "guardrails": rules.get("guardrails", []),
        }

        plan_file = output_dir / "hybrid_no_gpu_plan.json"
        plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        rag_manifest = self._build_rag_manifest(payload, rules)
        rag_file = output_dir / "rag_manifest.json"
        rag_file.write_text(json.dumps(rag_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        workflow_file = output_dir / "github_actions_ci.yml"
        workflow_file.write_text(self._render_github_actions(payload), encoding="utf-8")

        dockerfile = output_dir / "Dockerfile.cloudrun"
        dockerfile.write_text(self._render_cloudrun_dockerfile(), encoding="utf-8")

        return HybridStackResponse(
            product_name=payload.product_name,
            generated_at=generated_at,
            architecture_mode="hybrid_local_plus_free_cloud",
            estimated_fixed_cost="R$0 em baixo volume/free tier; custos podem surgir se exceder limites dos provedores.",
            output_dir=str(output_dir),
            plan_file=str(plan_file),
            github_actions_file=str(workflow_file),
            cloud_run_dockerfile=str(dockerfile),
            rag_manifest_file=str(rag_file),
            steps=steps,
            warnings=warnings,
        )

    def _build_steps(self, payload: HybridStackRequest) -> list[HybridStackStep]:
        media_mode = "external_gpu_free_tier" if payload.media_provider != "prompt_only" else "prompt_only"
        return [
            HybridStackStep(order=1, layer="Input", action="Receber DNA da oferta e tema", provider="AdIntelligence Strategic Input", mode="local"),
            HybridStackStep(order=2, layer="RAG", action="Recuperar regras V1/V2/V3, GEO, Pixel e padrões de copy", provider=payload.llm_provider, mode="rag_no_finetune", notes=["Sem fine-tuning pesado.", "Knowledge Core em JSON editável."]),
            HybridStackStep(order=3, layer="Imagem/Vídeo", action="Gerar prompts e payloads para render externo", provider=payload.media_provider, mode=media_mode, notes=["Colab/ComfyUI/Hugging Face assumem GPU quando necessário."]),
            HybridStackStep(order=4, layer="Render", action="Montar áudio/imagem/vídeo com FFmpeg quando houver assets", provider="FFmpeg CLI", mode="local_open_source"),
            HybridStackStep(order=5, layer="Deploy", action="Build/test via GitHub Actions e deploy serverless/estático", provider=payload.deploy_target, mode="scale_to_zero"),
            HybridStackStep(order=6, layer="Guardrails", action="Manter dry-run, Kill Switch e logs de decisão antes de publicação real", provider="Automation Control Center", mode="safety_first"),
        ]

    def _build_rag_manifest(self, payload: HybridStackRequest, rules: dict) -> dict:
        return {
            "rag_strategy": "retrieval_augmented_generation",
            "why": "Evita fine-tuning/GPU. A IA recebe contexto do Knowledge Core + histórico de conversões + criativos vencedores.",
            "llm_provider": payload.llm_provider,
            "recommended_cpu_models": rules.get("recommended_models_cpu", []),
            "sources": [
                "server/knowledge/v1_strategy.json",
                "server/knowledge/v2_strategy.json",
                "server/knowledge/v3_strategy.json",
                "server/knowledge/metrics_rules.json",
                "server/knowledge/copy_patterns.json",
                "server/knowledge/creative_patterns.json",
                "logs/capi_events.log",
                "decision_logs SQLite table",
            ],
            "retrieval_prompt_contract": {
                "input": "product_dna + campaign_goal + geo + latest_conversions",
                "output": "campaign_plan + creatives + copy + site + video_prompt + risk_flags",
                "style": "direto, prático, sem jargão desnecessário",
            },
        }

    def _render_github_actions(self, payload: HybridStackRequest) -> str:
        return """name: AdIntelligence CI Free Stack

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  test-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install API deps
        run: cd server && pip install -r requirements.txt
      - name: Run backend tests
        run: cd server && pytest -q
      - name: Install web deps
        run: npm run install:web
      - name: Build web
        run: npm run build:web
"""

    def _render_cloudrun_dockerfile(self) -> str:
        return """FROM python:3.11-slim
WORKDIR /app
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY server /app
ENV PORT=8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
"""
