from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.premium_render import PremiumRenderRequest
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.decision_feed_store import DecisionFeedStore


class PremiumRenderBridge:
    """Camada segura do PremiumRender.

    Missão 21:
    - Não chama providers externos.
    - Não executa Celery real.
    - Não executa FFmpeg real.
    - Não aciona Meta/TikTok/SiteBuilder.
    - Gera manifesto e payload de dry-run controlado.
    - Registra memória, DecisionFeed e Brain.
    """

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.project_root = project_root
        self.logs_dir = logs_dir or project_root / "logs"
        self.output_root = project_root / "data" / "campaign_kits" / "PremiumRenderSafe"
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.decision_feed = DecisionFeedStore(logs_dir=self.logs_dir)
        self.memory = CampaignMemoryStore(logs_dir=self.logs_dir)
        self.brain = CampaignBrainAgent(logs_dir=self.logs_dir)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": "PremiumRenderBridge",
            "mode": "premium_render_safe",
            "provider_forced": "dry_run",
            "dispatch_mode_forced": "local",
            "celery_real_enabled": False,
            "external_provider_enabled": False,
            "ffmpeg_real_enabled": False,
            "meta_real": False,
            "tiktok_real": False,
            "site_builder_enabled": False,
            "output_root": str(self.output_root),
        }

    def run_mock_cycle(self) -> dict[str, Any]:
        payload = PremiumRenderRequest(
            product_name="Ebook de Receitas Fitness",
            asset_type="image",
            prompt="Criativo premium para anúncio de ebook fitness, visual limpo, CTA forte, alto contraste social.",
            provider="dry_run",
            upscale=True,
            color_grade="warm_contrast",
            dispatch_mode="local",
            dry_run=True,
        )
        return self.safe_render(payload, product_name="Ebook de Receitas Fitness", niche="emagrecimento")

    def safe_render(self, payload: PremiumRenderRequest, product_name: str = "", niche: str = "") -> dict[str, Any]:
        now = datetime.now(UTC)
        render_id = f"{payload.product_name.lower().replace(' ', '-')}-{payload.asset_type}-{uuid4().hex[:8]}"
        output_dir = self.output_root / render_id
        output_dir.mkdir(parents=True, exist_ok=True)

        forced_payload = payload.model_dump(mode="json")
        forced_payload.update({
            "provider": "dry_run",
            "dispatch_mode": "local",
            "dry_run": True,
        })

        worker_payload_file = output_dir / "premium_render_safe_payload.json"
        manifest_file = output_dir / "premium_render_safe_manifest.json"
        brief_file = output_dir / "premium_render_safe_brief.md"

        worker_payload_file.write_text(json.dumps(forced_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        brief_file.write_text(self._brief_markdown(payload), encoding="utf-8")

        result = {
            "status": "ok",
            "agent": "PremiumRenderBridge",
            "mode": "safe_dry_run",
            "render_executed": False,
            "premium_render_real_executed": False,
            "external_provider_executed": False,
            "celery_executed": False,
            "ffmpeg_real_executed": False,
            "product_name": payload.product_name,
            "asset_type": payload.asset_type,
            "provider_forced": "dry_run",
            "dispatch_mode_forced": "local",
            "generated_at": now.isoformat(),
            "output_folder": str(output_dir),
            "worker_payload_file": str(worker_payload_file),
            "brief_file": str(brief_file),
            "final_file": None,
            "warnings": [
                "Dry-run seguro: PremiumRender real não foi executado.",
                "Providers externos bloqueados: flux/sdxl/runway/kling/local_ffmpeg não foram chamados.",
                "Celery real bloqueado.",
                "FFmpeg real bloqueado.",
                "Meta/TikTok/SiteBuilder permanecem desligados.",
            ],
            "next_action": "brain_review_before_premium_render_real",
        }

        manifest_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["manifest_file"] = str(manifest_file)

        memory_result = self._store_memory(payload, result, product_name, niche)
        decision_result = self._store_decision(payload, result, product_name, niche)
        brain_review = self._review_with_brain(payload, result, product_name, niche)

        return {
            "status": "ok",
            "agent": "PremiumRenderBridge",
            "mode": "premium_render_safe",
            "premium_render": result,
            "memory_result": memory_result,
            "decision_feed_result": decision_result,
            "brain_review": brain_review,
        }

    def _brief_markdown(self, payload: PremiumRenderRequest) -> str:
        return f"""# PremiumRender Safe — {payload.product_name}

Asset Type: {payload.asset_type}
Provider Forçado: dry_run
Dispatch Mode Forçado: local
Render real: não executado

## Prompt
{payload.prompt}

## Regras
- Não executar provider externo.
- Não executar Celery.
- Não executar FFmpeg real.
- Revisar com Brain antes de render premium real.
"""

    def _store_memory(self, payload: PremiumRenderRequest, result: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        return self.memory.remember({
            "product_name": product_name or payload.product_name,
            "niche": niche,
            "campaign_stage": "PREMIUM_RENDER_SAFE",
            "outcome": "SAFE_DRY_RUN",
            "lesson": "PremiumRender Safe gerou manifesto/payload sem executar render real.",
            "learning": "Antes de render premium real, validar provider, Celery, output local, custo e aprovação do Brain.",
            "metrics": {
                "render_executed": False,
                "external_provider_executed": False,
                "celery_executed": False,
                "ffmpeg_real_executed": False,
            },
            "source": "PremiumRenderBridge",
            "output_folder": result.get("output_folder"),
        })

    def _store_decision(self, payload: PremiumRenderRequest, result: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        record = {
            "product_name": product_name or payload.product_name,
            "campaign_stage": "PREMIUM_RENDER_SAFE",
            "decision": "SIM",
            "confidence": 82,
            "next_action": "brain_review_before_premium_render_real",
            "positive_points": [
                "PremiumRender Safe gerou payload e manifesto.",
                "Provider externo permaneceu bloqueado.",
                "Celery real permaneceu bloqueado.",
                "FFmpeg real permaneceu bloqueado.",
            ],
            "negative_points": result.get("warnings", []),
            "blocked_reasons": [],
            "meta_risk": {},
            "historical_recommendation": "Manter PremiumRender real bloqueado até validação de custo, provider e output.",
            "panoramic_view": "PremiumRender está preparado para etapa segura, sem execução pesada.",
            "recommended_solution": "Validar provider e dependências antes de liberar render premium real.",
            "memory_used": {"premium_render_safe": True, "render_real": False},
        }
        return self.decision_feed.record_brain_decision(record, context={
            "product_name": product_name or payload.product_name,
            "niche": niche,
            "campaign_stage": "PREMIUM_RENDER_SAFE",
        })

    def _review_with_brain(self, payload: PremiumRenderRequest, result: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        return self.brain.review_before_campaign({
            "product_name": product_name or payload.product_name,
            "niche": niche,
            "campaign_stage": "V4",
            "budget_brl": 25,
            "metrics": {"connect_rate": 80, "roas": 1.1, "purchase_rate": 2},
            "copy": payload.prompt,
            "offer": "PremiumRender Safe — dry run sem render premium real.",
            "premium_render_safe": result,
        })
