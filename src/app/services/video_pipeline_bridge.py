from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.video_pipeline import VideoRenderRequest
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.decision_feed_store import DecisionFeedStore


class VideoPipelineBridge:
    """Camada segura do VideoPipeline.

    Missão 19:
    - Não executa FFmpeg real por padrão.
    - Não chama ElevenLabs.
    - Não chama OpenAI TTS.
    - Não chama Meta.
    - Não chama TikTok.
    - Não aciona PremiumRender/SiteBuilder.
    - Registra memória, DecisionFeed e Brain.
    """

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.project_root = project_root
        self.logs_dir = logs_dir or project_root / "logs"
        self.output_root = project_root / "data" / "campaign_kits" / "VideoPipelineSafe"
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.decision_feed = DecisionFeedStore(logs_dir=self.logs_dir)
        self.memory = CampaignMemoryStore(logs_dir=self.logs_dir)
        self.brain = CampaignBrainAgent(logs_dir=self.logs_dir)

    def health(self) -> dict[str, Any]:
        ffmpeg_available = shutil.which("ffmpeg") is not None
        return {
            "status": "ok",
            "agent": "VideoPipelineBridge",
            "mode": "video_pipeline_safe",
            "ffmpeg_available": ffmpeg_available,
            "ffmpeg_real_enabled": False,
            "external_tts_enabled": False,
            "meta_real": False,
            "tiktok_real": False,
            "premium_render_enabled": False,
            "site_builder_enabled": False,
            "output_root": str(self.output_root),
        }

    def run_mock_cycle(self) -> dict[str, Any]:
        payload = VideoRenderRequest(
            product_name="Ebook de Receitas Fitness",
            model="V4",
            hook="Receitas práticas para organizar sua alimentação",
            script=(
                "Mostre a dor de não conseguir organizar a alimentação, apresente receitas simples "
                "e finalize com uma chamada direta para acessar o ebook agora."
            ),
            cta="Acesse agora",
            language="Português",
            aspect_ratio="9:16",
            voice_provider="fallback",
            scene_provider="ffmpeg_local",
            duration_seconds=8,
        )
        return self.safe_render(payload, product_name="Ebook de Receitas Fitness", niche="emagrecimento")

    def safe_render(self, payload: VideoRenderRequest, product_name: str = "", niche: str = "") -> dict[str, Any]:
        now = datetime.now(UTC)
        render_id = f"{payload.product_name.lower().replace(' ', '-')}-{payload.model.lower()}-{uuid4().hex[:8]}"
        output_dir = self.output_root / render_id
        output_dir.mkdir(parents=True, exist_ok=True)

        script_file = output_dir / "script.md"
        storyboard_file = output_dir / "storyboard.json"
        manifest_file = output_dir / "video_pipeline_safe_manifest.json"

        script_file.write_text(self._script_markdown(payload), encoding="utf-8")
        storyboard = self._storyboard(payload)
        storyboard_file.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")

        result = {
            "status": "ok",
            "agent": "VideoPipelineBridge",
            "mode": "safe_dry_run",
            "product_name": payload.product_name,
            "model": payload.model,
            "generated_at": now.isoformat(),
            "render_executed": False,
            "ffmpeg_real_executed": False,
            "external_tts_executed": False,
            "voice_provider_forced": "fallback",
            "scene_provider_blocked": payload.scene_provider,
            "output_folder": str(output_dir),
            "script_file": str(script_file),
            "storyboard_file": str(storyboard_file),
            "final_mp4": None,
            "warnings": [
                "Dry-run seguro: FFmpeg real não foi executado.",
                "Providers externos bloqueados: ElevenLabs/OpenAI TTS não foram chamados.",
                "PremiumRender/SiteBuilder/Meta/TikTok permanecem desligados.",
            ],
            "next_action": "brain_review_before_video_render_real",
        }
        manifest_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["manifest_file"] = str(manifest_file)

        memory_result = self._store_memory(payload, result, product_name, niche)
        decision_result = self._store_decision(payload, result, product_name, niche)
        brain_review = self._review_with_brain(payload, result, product_name, niche)

        return {
            "status": "ok",
            "agent": "VideoPipelineBridge",
            "mode": "video_pipeline_safe",
            "video_pipeline": result,
            "memory_result": memory_result,
            "decision_feed_result": decision_result,
            "brain_review": brain_review,
        }

    def _script_markdown(self, payload: VideoRenderRequest) -> str:
        return f"""# VideoPipeline Safe — {payload.product_name}

Modelo: {payload.model}
Formato: {payload.aspect_ratio}
Idioma: {payload.language}
Voice Provider Forçado: fallback
Render real: não executado

## Hook
{payload.hook}

## Script
{payload.script}

## CTA
{payload.cta}
"""

    def _storyboard(self, payload: VideoRenderRequest) -> dict[str, Any]:
        return {
            "product_name": payload.product_name,
            "model": payload.model,
            "aspect_ratio": payload.aspect_ratio,
            "scenes": [
                {"start": "0s", "role": "hook", "text": payload.hook},
                {"start": "3s", "role": "body", "text": payload.script[:500]},
                {"start": "final", "role": "cta", "text": payload.cta},
            ],
            "safe_mode": True,
            "render_real": False,
        }

    def _store_memory(self, payload: VideoRenderRequest, result: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        return self.memory.remember({
            "product_name": product_name or payload.product_name,
            "niche": niche,
            "campaign_stage": "VIDEO_SAFE",
            "outcome": "SAFE_DRY_RUN",
            "lesson": "VideoPipeline Safe gerou script/storyboard/manifest sem executar FFmpeg real.",
            "learning": "Antes de render real, confirmar FFmpeg, output local, peso do arquivo e aprovação do Brain.",
            "metrics": {
                "render_executed": False,
                "ffmpeg_real_executed": False,
                "external_tts_executed": False,
            },
            "source": "VideoPipelineBridge",
            "output_folder": result.get("output_folder"),
        })

    def _store_decision(self, payload: VideoRenderRequest, result: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        record = {
            "product_name": product_name or payload.product_name,
            "campaign_stage": "VIDEO_SAFE",
            "decision": "SIM",
            "confidence": 82,
            "next_action": "brain_review_before_video_render_real",
            "positive_points": [
                "VideoPipeline Safe gerou artefatos de planejamento.",
                "FFmpeg real permaneceu bloqueado.",
                "Providers externos permaneceram bloqueados.",
            ],
            "negative_points": result.get("warnings", []),
            "blocked_reasons": [],
            "meta_risk": {},
            "historical_recommendation": "Manter render real bloqueado até validação específica da Missão seguinte.",
            "panoramic_view": "VideoPipeline está preparado para etapa segura, sem execução pesada.",
            "recommended_solution": "Validar disponibilidade de FFmpeg e só depois liberar render controlado.",
            "memory_used": {"video_pipeline_safe": True, "render_real": False},
        }
        return self.decision_feed.record_brain_decision(record, context={
            "product_name": product_name or payload.product_name,
            "niche": niche,
            "campaign_stage": "VIDEO_SAFE",
        })

    def _review_with_brain(self, payload: VideoRenderRequest, result: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        return self.brain.review_before_campaign({
            "product_name": product_name or payload.product_name,
            "niche": niche,
            "campaign_stage": "V4",
            "budget_brl": 25,
            "metrics": {"connect_rate": 80, "roas": 1.1, "purchase_rate": 2},
            "copy": f"{payload.hook}\n{payload.script}\n{payload.cta}",
            "offer": "VideoPipeline Safe — dry run sem render real.",
            "video_safe": result,
        })
