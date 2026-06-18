from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings, safe_project_path
from app.schemas.zero_cost_stack import ZeroCostStackArtifact, ZeroCostStackRequest, ZeroCostStackResponse
from app.services.knowledge_engine import KnowledgeEngine


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or f"zero-cost-{uuid4().hex[:8]}"


class ZeroCostStackPlanner:
    """Gera a arquitetura prática de custo zero para IA multimídia sem GPU própria.

    O backend local mantém a lógica, prompts, RAG, guardrails e orquestração. Render
    pesado é enviado para Colab/ComfyUI/Hugging Face/Leonardo e build/deploy roda em
    GitHub Actions/serverless. Nada é executado em produção sem dry-run desligado.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.knowledge = KnowledgeEngine()
        self.output_root = safe_project_path(self.settings.orchestration_output_dir, "data/orchestration_runs") / "zero_cost_stack"
        self.output_root.mkdir(parents=True, exist_ok=True)

    def build(self, payload: ZeroCostStackRequest) -> ZeroCostStackResponse:
        generated_at = datetime.now(timezone.utc)
        output_dir = self.output_root / _slug(payload.product_name) / generated_at.strftime("%Y%m%d-%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)

        rules = self.knowledge.load("zero_cost_stack_rules")
        warnings = self._warnings(payload)
        execution_order = [
            "1. Receber tema/DNA da oferta no AdIntelligence Pro.",
            "2. Buscar contexto no Knowledge Core via RAG, sem fine-tuning.",
            "3. Gerar JSON maestro com hooks, copies, cenas, prompts e assets esperados.",
            "4. Enviar render pesado para Colab/ComfyUI/Hugging Face/Leonardo quando necessário.",
            "5. Montar vídeo localmente com FFmpeg quando os assets voltarem.",
            "6. Gerar landing/site estático e acionar GitHub Actions/Vercel/Netlify se liberado.",
            "7. Registrar decisão no Decision Feed e manter dry-run até validação humana.",
        ]

        master_json = self._build_master_json(payload, rules, generated_at)
        master_path = output_dir / "pipeline_master.json"
        master_path.write_text(json.dumps(master_json, ensure_ascii=False, indent=2), encoding="utf-8")

        gemini_prompt_path = output_dir / "gemini_rag_prompt.md"
        gemini_prompt_path.write_text(self._render_gemini_prompt(payload, rules), encoding="utf-8")

        colab_path = output_dir / "colab_comfyui_runner.ipynb.json"
        colab_path.write_text(json.dumps(self._render_colab_notebook(payload), ensure_ascii=False, indent=2), encoding="utf-8")

        bash_path = output_dir / "run_zero_cost_pipeline.sh"
        bash_path.write_text(self._render_bash_runner(), encoding="utf-8")

        n8n_path = output_dir / "n8n_zero_cost_workflow.json"
        n8n_path.write_text(json.dumps(self._render_n8n_workflow(payload), ensure_ascii=False, indent=2), encoding="utf-8")

        github_actions_path = output_dir / "github_actions_free_deploy.yml"
        github_actions_path.write_text(self._render_github_actions(), encoding="utf-8")

        artifacts = [
            ZeroCostStackArtifact(name="pipeline_master.json", path=str(master_path), purpose="Contrato central para todos os passos da automação."),
            ZeroCostStackArtifact(name="gemini_rag_prompt.md", path=str(gemini_prompt_path), purpose="Prompt de inteligência usando Gemini/RAG ou fallback Ollama."),
            ZeroCostStackArtifact(name="colab_comfyui_runner.ipynb.json", path=str(colab_path), purpose="Notebook-base para render de imagem/vídeo em Colab."),
            ZeroCostStackArtifact(name="run_zero_cost_pipeline.sh", path=str(bash_path), purpose="Cola Bash para disparar webhooks e organizar saídas."),
            ZeroCostStackArtifact(name="n8n_zero_cost_workflow.json", path=str(n8n_path), purpose="Workflow n8n importável para orquestração visual."),
            ZeroCostStackArtifact(name="github_actions_free_deploy.yml", path=str(github_actions_path), purpose="Build/test/deploy gratuito via GitHub Actions."),
        ]

        return ZeroCostStackResponse(
            product_name=payload.product_name,
            generated_at=generated_at,
            mode="hybrid_zero_cost_no_gpu",
            output_dir=str(output_dir),
            fixed_cost_strategy="Backend local + render externo gratuito + GitHub Actions/serverless scale-to-zero.",
            execution_order=execution_order,
            artifacts=artifacts,
            guardrails=rules.get("guardrails", []),
            warnings=warnings,
        )

    def _warnings(self, payload: ZeroCostStackRequest) -> list[str]:
        warnings: list[str] = []
        if not payload.dry_run:
            warnings.append("Dry-run desligado: valide tokens, Kill Switch e limites antes de executar qualquer deploy/publicação real.")
        if payload.llm_provider == "gemini_free" and not self.settings.google_gemini_api_key:
            warnings.append("GOOGLE_GEMINI_API_KEY ausente: usar fallback local_template/Ollama CPU até configurar Gemini.")
        if payload.render_provider == "google_colab_comfyui" and not self.settings.colab_notebook_url:
            warnings.append("COLAB_NOTEBOOK_URL ausente: o plano gerou notebook-base, mas execução será manual ou via URL configurada depois.")
        if payload.orchestrator.startswith("n8n") and not self.settings.n8n_base_url:
            warnings.append("N8N_BASE_URL ausente: workflow foi gerado, mas webhook real ainda não será chamado.")
        return warnings

    def _build_master_json(self, payload: ZeroCostStackRequest, rules: dict, generated_at: datetime) -> dict:
        return {
            "schema_version": "1.0",
            "generated_at": generated_at.isoformat(),
            "product_name": payload.product_name,
            "theme": payload.theme,
            "campaign_goal": payload.campaign_goal,
            "providers": {
                "llm": payload.llm_provider,
                "render": payload.render_provider,
                "orchestrator": payload.orchestrator,
                "deploy": payload.deploy_provider,
            },
            "cost_policy": rules.get("cost_policy", {}),
            "pipeline": {
                "input": "product_dna + offer + geo + language + validated_ads",
                "rag": "Knowledge Core JSON + decision logs + CAPI events",
                "llm_output": "hooks + copy + scenes + image_prompts + video_script + landing_sections",
                "render_output": "images/videos returned from Colab/HF/Leonardo or prompt-only fallback",
                "assembly": "FFmpeg + Site Builder + War Kit folders",
                "deploy": "GitHub Actions -> Vercel/Netlify/Cloud Run, dry-run by default",
            },
            "artifacts_expected": ["copies", "pdfs", "image_prompts", "video_scripts", "mp4", "site", "meta_payload"],
            "guardrails": rules.get("guardrails", []),
        }

    def _render_gemini_prompt(self, payload: ZeroCostStackRequest, rules: dict) -> str:
        return f"""# Gemini/RAG Prompt — AdIntelligence Pro

Você é o motor estratégico do AdIntelligence Pro. Use APENAS o contexto recuperado do Knowledge Core, logs de decisão, CAPI e anúncios validados.

Produto: {payload.product_name}
Tema: {payload.theme}
Objetivo: {payload.campaign_goal}

Regras obrigatórias:
- Não fazer fine-tuning.
- Usar RAG e citar internamente quais regras foram usadas.
- Gerar saída JSON, nunca texto solto.
- Priorizar V1/V2/V3 quando for teste e V4/V5/V6 quando houver conversões reais.
- Manter tom direto, prático e orientado a ação.

Contrato de saída:
{{
  "hooks": [],
  "copies": [],
  "image_prompts": [],
  "video_scenes": [],
  "landing_sections": [],
  "risk_flags": [],
  "next_actions": []
}}

Guardrails ativos:
{json.dumps(rules.get('guardrails', []), ensure_ascii=False, indent=2)}
"""

    def _render_colab_notebook(self, payload: ZeroCostStackRequest) -> dict:
        return {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"name": f"AdIntelligence_Colab_ComfyUI_{_slug(payload.product_name)}"},
            "cells": [
                {"cell_type": "markdown", "metadata": {}, "source": ["# AdIntelligence Pro — Colab/ComfyUI Runner\\n", "Execute render pesado fora do seu PC local.\\n"]},
                {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["# Cole aqui o pipeline_master.json gerado pelo AdIntelligence Pro\\n", "PIPELINE = {}\\n"]},
                {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["# Aqui você pode conectar ComfyUI/Stable Diffusion/Stable Video Diffusion\\n", "# Saída esperada: assets renderizados para baixar e devolver ao War Kit.\\n", "print('Ready for external GPU render')\\n"]},
            ],
        }

    def _render_bash_runner(self) -> str:
        return """#!/usr/bin/env bash
set -euo pipefail

PIPELINE_JSON="${1:-pipeline_master.json}"
API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
N8N_WEBHOOK_URL="${N8N_WEBHOOK_URL:-}"

echo "[AdIntelligence] Validando pipeline: ${PIPELINE_JSON}"
test -f "$PIPELINE_JSON"

if [ -n "$N8N_WEBHOOK_URL" ]; then
  echo "[AdIntelligence] Enviando para n8n..."
  curl -sS -X POST "$N8N_WEBHOOK_URL" -H "Content-Type: application/json" --data-binary "@${PIPELINE_JSON}"
else
  echo "[AdIntelligence] N8N_WEBHOOK_URL vazio. Rodando em modo local/dry-run."
fi

echo "[AdIntelligence] Pipeline finalizado em modo seguro."
"""

    def _render_n8n_workflow(self, payload: ZeroCostStackRequest) -> dict:
        return {
            "name": "AdIntelligence Zero-Cost AI Pipeline",
            "nodes": [
                {"name": "Webhook Input", "type": "n8n-nodes-base.webhook", "parameters": {"path": "adintelligence-zero-cost", "httpMethod": "POST"}},
                {"name": "Validate Master JSON", "type": "n8n-nodes-base.function", "parameters": {"functionCode": "return items;"}},
                {"name": "Route Render Jobs", "type": "n8n-nodes-base.noOp", "parameters": {}},
                {"name": "Notify Decision Feed", "type": "n8n-nodes-base.httpRequest", "parameters": {"method": "POST", "url": "http://localhost:8000/api/v1/orchestration/run"}},
            ],
            "connections": {},
            "settings": {"dryRun": payload.dry_run},
        }

    def _render_github_actions(self) -> str:
        return """name: AdIntelligence Free Stack CI

on:
  workflow_dispatch:
  push:
    branches: [ main ]

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
      - name: Install backend
        run: cd server && pip install -r requirements.txt
      - name: Test backend
        run: cd server && pytest -q
      - name: Build frontend
        run: npm run install:web && npm run build:web
"""
