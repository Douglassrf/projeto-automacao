from __future__ import annotations

from pathlib import Path
from typing import Any

from app.schemas.content_orchestrator import ContentOrchestratorRequest, ExistingContentItem
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.content_orchestrator import ContentOrchestrator
from app.services.decision_feed_store import DecisionFeedStore


class ContentOrchestratorBridge:
    """Ponte segura: ContentOrchestrator -> DecisionFeed -> CampaignMemory -> Brain.

    Missão 17:
    - Não executa VideoPipeline.
    - Não executa PremiumRender.
    - Não executa SiteBuilder.
    - Não chama Meta real.
    - Não chama TikTok.
    - Apenas roteia, registra e pede revisão ao Brain.
    """

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.logs_dir = logs_dir or project_root / "logs"
        self.orchestrator = ContentOrchestrator()
        self.decision_feed = DecisionFeedStore(logs_dir=self.logs_dir)
        self.memory = CampaignMemoryStore(logs_dir=self.logs_dir)
        self.brain = CampaignBrainAgent(logs_dir=self.logs_dir)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": "ContentOrchestratorBridge",
            "mode": "content_orchestrator_safe",
            "video_pipeline_enabled": False,
            "premium_render_enabled": False,
            "site_builder_enabled": False,
            "meta_real": False,
            "tiktok_real": False,
        }

    def run_mock_cycle(self) -> dict[str, Any]:
        payload = ContentOrchestratorRequest(
            title="Vídeo UGC para Ebook de Receitas Fitness",
            brief=(
                "Criar vídeo curto para público de emagrecimento e rotina saudável. "
                "A dor é falta de organização na alimentação, o benefício é ter receitas práticas, "
                "com CTA para acessar agora, prova por ROAS e Connect Rate, e linguagem simples para avatar iniciante."
            ),
            target_platform="Meta Ads",
            desired_format="auto",
            existing_content=[
                ExistingContentItem(
                    title="Imagem de anúncio para ebook de marketing",
                    summary="Criativo antigo sobre afiliados e tráfego."
                )
            ],
            quality_threshold=8.0,
        )
        return self.run_cycle(payload=payload, product_name="Ebook de Receitas Fitness", niche="emagrecimento")

    def run_cycle(self, payload: ContentOrchestratorRequest, product_name: str = "", niche: str = "") -> dict[str, Any]:
        route_result = self.orchestrator.route(payload)
        route_data = route_result.model_dump(mode="json")

        memory_result = self._store_memory(payload=payload, route_data=route_data, product_name=product_name, niche=niche)
        decision_result = self._store_decision(payload=payload, route_data=route_data, product_name=product_name, niche=niche)
        brain_review = self._review_with_brain(payload=payload, route_data=route_data, product_name=product_name, niche=niche)

        return {
            "status": "ok",
            "agent": "ContentOrchestratorBridge",
            "mode": "safe",
            "factory_executed": False,
            "video_pipeline_executed": False,
            "premium_render_executed": False,
            "site_builder_executed": False,
            "meta_real": False,
            "tiktok_real": False,
            "content_orchestrator": route_data,
            "memory_result": memory_result,
            "decision_feed_result": decision_result,
            "brain_review": brain_review,
        }

    def _store_memory(self, payload: ContentOrchestratorRequest, route_data: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        generated = route_data.get("generated_payload") or {}
        content_type = generated.get("type") or "unknown"
        status = route_data.get("status")
        lesson = (
            f"ContentOrchestrator avaliou brief com status {status}, tipo {content_type}, "
            f"próximo passo {route_data.get('proximo_passo')}."
        )
        return self.memory.remember({
            "product_name": product_name or payload.title,
            "niche": niche,
            "campaign_stage": "CONTENT_SAFE",
            "outcome": "WINNER" if status == "ok" else "BLOCKED",
            "lesson": lesson,
            "learning": "Conteúdo deve ser roteado e revisado pelo Brain antes de qualquer execução de fábrica.",
            "metrics": {
                "quality_score": (route_data.get("log") or {}).get("qualidade_nota"),
                "quality_threshold": (route_data.get("log") or {}).get("threshold"),
            },
            "content_type": content_type,
            "next_tool": route_data.get("proximo_passo"),
            "source": "ContentOrchestratorBridge",
        })

    def _store_decision(self, payload: ContentOrchestratorRequest, route_data: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        log = route_data.get("log") or {}
        generated = route_data.get("generated_payload") or {}
        decision = "SIM" if route_data.get("status") == "ok" else "NÃO"
        record = {
            "product_name": product_name or payload.title,
            "campaign_stage": "CONTENT_SAFE",
            "decision": decision,
            "confidence": 84 if decision == "SIM" else 60,
            "next_action": "brain_review_before_factory" if decision == "SIM" else "melhorar_brief",
            "positive_points": [
                f"Tipo decidido: {generated.get('type', 'unknown')}.",
                f"Próxima ferramenta sugerida: {route_data.get('proximo_passo')}.",
                f"Nota de qualidade: {log.get('qualidade_nota')}.",
            ],
            "negative_points": log.get("melhorias", []) if decision != "SIM" else [],
            "blocked_reasons": ["duplicate_or_low_quality"] if decision != "SIM" else [],
            "meta_risk": {},
            "historical_recommendation": "Não executar fábrica antes da revisão do Brain.",
            "panoramic_view": "ContentOrchestrator roteou o conteúdo e gerou payload, mas a fábrica permaneceu desligada.",
            "recommended_solution": "Registrar decisão, revisar pelo Brain e avançar somente em dry_run.",
            "memory_used": {
                "content_orchestrator": True,
                "factory_executed": False,
            },
        }
        return self.decision_feed.record_brain_decision(record, context={
            "product_name": product_name or payload.title,
            "niche": niche,
            "campaign_stage": "CONTENT_SAFE",
        })

    def _review_with_brain(self, payload: ContentOrchestratorRequest, route_data: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        generated = route_data.get("generated_payload") or {}
        log = route_data.get("log") or {}
        return self.brain.review_before_campaign({
            "product_name": product_name or payload.title,
            "niche": niche,
            "campaign_stage": "V1",
            "budget_brl": 25,
            "metrics": {
                "connect_rate": 80 if route_data.get("status") == "ok" else 0,
                "roas": 1.1 if route_data.get("status") == "ok" else 0,
            },
            "copy": generated.get("prompt_midia") or str(generated.get("copy") or payload.brief),
            "offer": "ContentOrchestrator Safe — payload gerado sem execução de fábrica.",
            "content_quality_score": log.get("qualidade_nota"),
            "content_type": generated.get("type"),
            "next_tool": route_data.get("proximo_passo"),
        })
