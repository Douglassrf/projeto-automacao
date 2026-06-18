from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.orchestration import OrchestrationRequest, OrchestrationResponse, OrchestrationStep
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.content_orchestrator_bridge import ContentOrchestratorBridge
from app.services.decision_feed_store import DecisionFeedStore
from app.services.master_context import MasterContextStore
from app.services.premium_render_bridge import PremiumRenderBridge
from app.services.site_builder_bridge import SiteBuilderBridge
from app.services.video_pipeline_bridge import VideoPipelineBridge


class OrchestrationPipelineSafe:
    """Orquestração segura da fábrica.

    Missão 24B:
    - Usa apenas bridges Safe homologados.
    - Não chama Meta real.
    - Não chama TikTok real.
    - Não executa render real.
    - Não executa deploy real.
    - Não usa legacy.NoOp.
    - Retorna OrchestrationResponse válido.
    """

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.project_root = project_root
        self.logs_dir = logs_dir or project_root / "logs"
        self.output_root = project_root / "data" / "campaign_kits" / "OrchestrationSafe"
        self.output_root.mkdir(parents=True, exist_ok=True)

        self.master_context = MasterContextStore()
        self.decision_feed = DecisionFeedStore(logs_dir=self.logs_dir)
        self.memory = CampaignMemoryStore(logs_dir=self.logs_dir)
        self.brain = CampaignBrainAgent(logs_dir=self.logs_dir)

        self.content = ContentOrchestratorBridge(logs_dir=self.logs_dir)
        self.video = VideoPipelineBridge(logs_dir=self.logs_dir)
        self.premium = PremiumRenderBridge(logs_dir=self.logs_dir)
        self.site = SiteBuilderBridge(logs_dir=self.logs_dir)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": "OrchestrationPipelineSafe",
            "mode": "orchestration_safe",
            "meta_real": False,
            "tiktok_real": False,
            "render_real": False,
            "deploy_real": False,
            "uses_legacy_noop": False,
            "output_root": str(self.output_root),
        }

    def run_mock_cycle(self) -> OrchestrationResponse:
        from app.schemas.orchestration import OrchestrationRequest
        from app.schemas.war_kit import ProductDNAInput

        payload = OrchestrationRequest(
            product=ProductDNAInput(
                product_name="Ebook de Receitas Fitness",
                niche="emagrecimento",
                offer_promise="Receitas práticas para organizar sua alimentação.",
                target_avatar="Pessoas ocupadas que querem comer melhor sem complicar.",
                main_pain="Falta de tempo e dificuldade de manter rotina alimentar.",
                desired_transformation="Ter um plano simples de receitas e organização semanal.",
                ticket_price=27,
                pixel_id="123456789",
                landing_page_url="https://example.com/landing",
                checkout_url="https://checkout.example.com/ebook-receitas-fitness",
                affiliate_link="https://checkout.example.com/ebook-receitas-fitness?aff=test",
                language="pt",
                geo_preset="BRAZIL",
                countries=["BR"],
                excluded_countries=[],
                platform="Hotmart/Kiwify",
            ),
            run_mode="dry_run",
            include_site=True,
            include_video=True,
            include_images=True,
            include_deploy_payload=True,
            deploy_provider="github_vercel",
        )
        return self.run(payload)

    def run(self, payload: OrchestrationRequest) -> OrchestrationResponse:
        now = datetime.now(UTC)
        product = payload.product
        run_id = f"{self._slug(product.product_name)}-{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        output_dir = self.output_root / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        steps: list[OrchestrationStep] = []
        warnings: list[str] = []

        pipeline_json = output_dir / "pipeline.json"
        bash_runner = output_dir / "run.sh"
        n8n_workflow = output_dir / "n8n_workflow.json"
        manifest_file = output_dir / "orchestration_manifest.json"

        plan = self._pipeline_plan(payload, run_id)
        pipeline_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        bash_runner.write_text(self._bash_runner(payload, pipeline_json, manifest_file), encoding="utf-8")
        n8n_workflow.write_text(json.dumps(self._n8n_workflow(payload, run_id), ensure_ascii=False, indent=2), encoding="utf-8")

        steps.append(self._step(1, "MasterContext Startup Checklist", "MasterContextStore", "ok", str(self.logs_dir), ["Memória mestre consultada em modo seguro."]))
        try:
            self.master_context.ensure_initialized()
        except Exception as exc:
            warnings.append(f"MasterContext não inicializou completamente: {exc}")

        if payload.run_mode == "plan_only":
            warnings.append("plan_only: nenhum bridge Safe foi executado; apenas pipeline.json, run.sh e n8n_workflow.json foram gerados.")
            manifest = self._manifest(payload, run_id, output_dir, steps, warnings, executed_bridges={})
            manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._response(payload, now, output_dir, pipeline_json, bash_runner, n8n_workflow, steps, warnings)

        executed: dict[str, Any] = {}

        content_result = self.content.run_mock_cycle()
        executed["content_orchestrator_safe"] = self._compact(content_result)
        steps.append(self._step(2, "ContentOrchestrator Safe", "ContentOrchestratorBridge", "ok", self._get_nested(content_result, "content_orchestrator", "proximo_passo"), ["Roteamento de conteúdo executado em modo safe."]))

        if payload.include_video:
            video_result = self.video.run_mock_cycle()
            executed["video_pipeline_safe"] = self._compact(video_result)
            video_output = self._get_nested(video_result, "video_pipeline", "manifest_file")
            steps.append(self._step(3, "VideoPipeline Safe", "VideoPipelineBridge", "ok", video_output, ["Render real bloqueado."]))
        else:
            steps.append(self._step(3, "VideoPipeline Safe", "VideoPipelineBridge", "skipped", None, ["include_video=false."]))

        if payload.include_images:
            premium_result = self.premium.run_mock_cycle()
            executed["premium_render_safe"] = self._compact(premium_result)
            premium_output = self._get_nested(premium_result, "premium_render", "manifest_file")
            steps.append(self._step(4, "PremiumRender Safe", "PremiumRenderBridge", "ok", premium_output, ["Provider externo, Celery e FFmpeg real bloqueados."]))
        else:
            steps.append(self._step(4, "PremiumRender Safe", "PremiumRenderBridge", "skipped", None, ["include_images=false."]))

        site_preview = None
        deploy_payload = None
        if payload.include_site:
            site_result = self.site.run_mock_cycle()
            executed["site_builder_safe"] = self._compact(site_result)
            site_preview = self._get_nested(site_result, "site_builder", "preview_path")
            deploy_payload = self._get_nested(site_result, "site_builder", "deploy_payload_path")
            steps.append(self._step(5, "SiteBuilder Safe", "SiteBuilderBridge", "ok", site_preview, ["Deploy real bloqueado."]))
        else:
            steps.append(self._step(5, "SiteBuilder Safe", "SiteBuilderBridge", "skipped", None, ["include_site=false."]))

        memory_result = self.memory.remember({
            "product_name": product.product_name,
            "niche": product.niche,
            "campaign_stage": "ORCHESTRATION_SAFE",
            "outcome": "SAFE_DRY_RUN",
            "lesson": "OrchestrationPipeline Safe conectou os bridges Safe sem render/deploy/publicação real.",
            "learning": "A fábrica completa pode avançar para dry-run geral mantendo todos os bloqueios reais ativos.",
            "metrics": {
                "steps": len(steps),
                "run_mode": payload.run_mode,
                "meta_real": False,
                "deploy_real": False,
                "render_real": False,
            },
            "source": "OrchestrationPipelineSafe",
            "output_dir": str(output_dir),
        })
        steps.append(self._step(6, "CampaignMemory", "CampaignMemoryStore", memory_result.get("status", "ok"), None, ["Memória registrada."]))

        decision_result = self.decision_feed.record_brain_decision({
            "product_name": product.product_name,
            "campaign_stage": "ORCHESTRATION_SAFE",
            "decision": "SIM",
            "confidence": 86,
            "next_action": "factory_complete_dry_run",
            "positive_points": [
                "Bridges Safe executados em sequência.",
                "OrchestrationResponse válido produzido.",
                "Render/deploy/publicação reais permaneceram bloqueados.",
            ],
            "negative_points": warnings,
            "blocked_reasons": [],
            "meta_risk": {},
            "historical_recommendation": "Prosseguir para Missão 25 com Fábrica Completa Dry Run.",
            "panoramic_view": "Orquestração central reparada em camada safe.",
            "recommended_solution": "Validar dry-run geral antes de qualquer execução real.",
            "memory_used": {"orchestration_safe": True},
        }, context={
            "product_name": product.product_name,
            "niche": product.niche,
            "campaign_stage": "ORCHESTRATION_SAFE",
        })
        steps.append(self._step(7, "DecisionFeed", "DecisionFeedStore", decision_result.get("status", "ok"), None, ["Decisão registrada."]))

        brain_review = self.brain.review_before_campaign({
            "product_name": product.product_name,
            "niche": product.niche,
            "campaign_stage": "V4",
            "budget_brl": 25,
            "metrics": {"connect_rate": 80, "roas": 1.1, "purchase_rate": 2},
            "copy": product.offer_promise,
            "offer": "OrchestrationPipeline Safe — fábrica conectada em dry-run.",
            "orchestration_safe": {"run_id": run_id, "output_dir": str(output_dir), "steps": len(steps)},
        })
        steps.append(self._step(8, "CampaignBrain", "CampaignBrainAgent", brain_review.get("decision", "reviewed"), brain_review.get("next_action"), ["Brain revisou a orquestração safe."]))

        manifest = self._manifest(payload, run_id, output_dir, steps, warnings, executed_bridges=executed)
        manifest["memory_result"] = memory_result
        manifest["decision_feed_result"] = decision_result
        manifest["brain_review"] = brain_review
        manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        response = self._response(payload, now, output_dir, pipeline_json, bash_runner, n8n_workflow, steps, warnings)
        response.site_preview = site_preview
        response.deploy_payload = deploy_payload
        response.war_kit_folder = str(output_dir)
        response.video_mp4 = self._get_nested(executed.get("video_pipeline_safe", {}), "video_pipeline", "manifest_file")
        return response

    def _response(self, payload: OrchestrationRequest, generated_at: datetime, output_dir: Path, pipeline_json: Path, bash_runner: Path, n8n_workflow: Path, steps: list[OrchestrationStep], warnings: list[str]) -> OrchestrationResponse:
        return OrchestrationResponse(
            product_name=payload.product.product_name,
            generated_at=generated_at,
            run_mode=payload.run_mode,
            output_dir=str(output_dir),
            pipeline_json=str(pipeline_json),
            bash_runner=str(bash_runner),
            n8n_workflow=str(n8n_workflow),
            steps=steps,
            war_kit_folder=None,
            site_preview=None,
            video_mp4=None,
            deploy_payload=None,
            warnings=warnings,
        )

    def _pipeline_plan(self, payload: OrchestrationRequest, run_id: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "workflow_name": payload.workflow_name,
            "run_mode": payload.run_mode,
            "product_name": payload.product.product_name,
            "safe_guards": {
                "meta_real": False,
                "tiktok_real": False,
                "render_real": False,
                "deploy_real": False,
                "providers_external": False,
            },
            "steps": [
                "master_context",
                "content_orchestrator_safe",
                "video_pipeline_safe" if payload.include_video else "video_pipeline_skipped",
                "premium_render_safe" if payload.include_images else "premium_render_skipped",
                "site_builder_safe" if payload.include_site else "site_builder_skipped",
                "campaign_memory",
                "decision_feed",
                "campaign_brain",
            ],
        }

    def _bash_runner(self, payload: OrchestrationRequest, pipeline_json: Path, manifest_file: Path) -> str:
        return f"""#!/usr/bin/env bash
set -euo pipefail
echo "Orchestration Safe — {payload.product.product_name}"
echo "Pipeline: {pipeline_json}"
echo "Manifest: {manifest_file}"
echo "SAFE MODE: no real render, no real deploy, no Meta, no TikTok"
"""

    def _n8n_workflow(self, payload: OrchestrationRequest, run_id: str) -> dict[str, Any]:
        return {
            "name": f"{payload.workflow_name} — SAFE",
            "run_id": run_id,
            "active": False,
            "nodes": [
                {"name": "Start Safe", "type": "manualTrigger"},
                {"name": "Read Pipeline JSON", "type": "readFile"},
                {"name": "Call Local API Dry Run", "type": "httpRequest", "disabled": True},
            ],
            "notes": "Blueprint n8n gerado em dry-run. Nenhum webhook externo foi chamado.",
        }

    def _manifest(self, payload: OrchestrationRequest, run_id: str, output_dir: Path, steps: list[OrchestrationStep], warnings: list[str], executed_bridges: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "product_name": payload.product.product_name,
            "run_mode": payload.run_mode,
            "output_dir": str(output_dir),
            "safe_mode": True,
            "executed_bridges": executed_bridges,
            "steps": [step.model_dump(mode="json") for step in steps],
            "warnings": warnings,
            "blocked": {
                "meta_real": True,
                "tiktok_real": True,
                "render_real": True,
                "deploy_real": True,
                "external_providers": True,
            },
        }

    def _step(self, order: int, name: str, tool: str, status: str, output: str | None, notes: list[str]) -> OrchestrationStep:
        return OrchestrationStep(order=order, name=name, tool=tool, status=str(status), output=output, notes=notes)

    def _slug(self, value: str) -> str:
        return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")[:80] or "product"

    def _get_nested(self, data: dict[str, Any], *keys: str) -> Any:
        cur: Any = data
        for key in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
        return cur

    def _compact(self, data: dict[str, Any]) -> dict[str, Any]:
        compact = {"status": data.get("status"), "agent": data.get("agent"), "mode": data.get("mode")}
        for key in ("content_orchestrator", "video_pipeline", "premium_render", "site_builder"):
            if key in data:
                compact[key] = data[key]
        if "brain_review" in data:
            compact["brain_review"] = {
                "decision": data["brain_review"].get("decision"),
                "next_action": data["brain_review"].get("next_action"),
            }
        return compact


class FreeStackOrchestrator(OrchestrationPipelineSafe):
    """Compatibilidade: a rota antiga passa a usar o pipeline safe."""
    pass
