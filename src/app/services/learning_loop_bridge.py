from __future__ import annotations

from pathlib import Path
from typing import Any

from app.schemas.learning_loop import CapiIngestRequest, ConversionEventInput, LearningLoopRequest
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.decision_feed_store import DecisionFeedStore
from app.services.learning_loop import CapiLearningLoopService


class LearningLoopBrainBridge:
    """Ponte segura: LearningLoop -> DecisionFeed -> CampaignMemory -> Brain.

    Missão 14:
    - Não publica campanha.
    - Não chama API Meta.
    - Não usa TikTok.
    - Não aciona VideoPipeline/PremiumRender.
    - Usa output local seguro.
    """

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.logs_dir = logs_dir or project_root / "logs"
        self.output_dir = project_root / "data" / "campaign_kits"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.decision_feed = DecisionFeedStore(logs_dir=self.logs_dir)
        self.memory = CampaignMemoryStore(logs_dir=self.logs_dir)
        self.brain = CampaignBrainAgent(logs_dir=self.logs_dir)

    def _learning_service(self) -> CapiLearningLoopService:
        service = CapiLearningLoopService()
        service.settings.kit_output_dir = str(self.output_dir)
        return service

    def run_mock_cycle(self) -> dict[str, Any]:
        event = ConversionEventInput(
            event_id="evt-bridge-learning-001",
            pixel_id="PIXEL_MOCK_123",
            campaign_id="camp-bridge-v3",
            campaign_name="Ebook de Receitas Fitness V3 AD01",
            ad_id="ad-bridge-001",
            ad_name="AD01 Hook Praticidade",
            creative_id="creative-winner-bridge-001",
            creative_name="Criativo campeão ponte",
            product_name="Ebook de Receitas Fitness",
            geo="BRASIL",
            language="Portuguese_All",
            value=147.0,
            currency="BRL",
            purchase_count=2,
            cpa=24.5,
            roas=4.2,
            connect_rate=86.0,
            checkout_rate=28.0,
            hook="Receitas práticas para organizar sua alimentação",
            copy_text="Copy vencedora baseada em praticidade, rotina e promessa moderada.",
            creative_pattern="UGC simples com prova visual, benefício direto e CTA discreto",
            final_url="https://checkout.exemplo.com/ebook-receitas-fitness",
        )

        return self.run_cycle(
            product_name="Ebook de Receitas Fitness",
            niche="emagrecimento",
            event=event,
            request=LearningLoopRequest(
                product_name="Ebook de Receitas Fitness",
                min_roas=1.0,
                min_purchases=1,
                max_winners=5,
                generate_versions=["V4", "V5", "V6"],
                prepare_war_kit=True,
            ),
        )

    def run_cycle(
        self,
        product_name: str,
        niche: str,
        event: ConversionEventInput,
        request: LearningLoopRequest,
    ) -> dict[str, Any]:
        service = self._learning_service()
        ingest = service.ingest_capi_events(CapiIngestRequest(events=[event], forward_to_meta=False))
        loop_response = service.run_learning_loop(request)
        loop_data = loop_response.model_dump(mode="json")

        memory_result = self._store_learning_memory(product_name=product_name, niche=niche, loop_data=loop_data)
        decision_result = self.decision_feed.record_learning_loop_decision(
            loop_data,
            context={
                "product_name": product_name,
                "niche": niche,
                "campaign_stage": "V4_V5_V6",
            },
        )
        brain_review = self._review_generated_variations(product_name=product_name, niche=niche, loop_data=loop_data)

        return {
            "status": "ok",
            "agent": "LearningLoopBrainBridge",
            "mode": "learning_loop_to_brain_safe",
            "meta_real": False,
            "publish_real": False,
            "ingest": ingest.model_dump(mode="json"),
            "learning_loop": loop_data,
            "memory_result": memory_result,
            "decision_feed_result": decision_result,
            "brain_review": brain_review,
        }

    def _store_learning_memory(self, product_name: str, niche: str, loop_data: dict[str, Any]) -> dict[str, Any]:
        winners = loop_data.get("winners", []) or []
        variations = loop_data.get("generated_variations", []) or []
        top_winner = winners[0] if winners else {}
        lesson = "LearningLoop gerou variações a partir de criativo vencedor."
        if top_winner:
            lesson = (
                f"Criativo {top_winner.get('ad_name')} venceu com ROAS {top_winner.get('avg_roas')} "
                f"e Connect Rate {top_winner.get('avg_connect_rate')}."
            )
        return self.memory.remember({
            "product_name": product_name,
            "niche": niche,
            "campaign_stage": "V4_V5_V6",
            "outcome": "WINNER" if variations else "UNKNOWN",
            "lesson": lesson,
            "learning": "Variações geradas pelo LearningLoop devem passar pelo Brain antes de dry_run.",
            "metrics": {
                "total_events_used": loop_data.get("total_events_used"),
                "winners_count": len(winners),
                "variations_count": len(variations),
                "top_roas": top_winner.get("avg_roas"),
                "top_connect_rate": top_winner.get("avg_connect_rate"),
            },
            "variations": [item.get("version") for item in variations],
            "source": "LearningLoopBrainBridge",
        })

    def _review_generated_variations(self, product_name: str, niche: str, loop_data: dict[str, Any]) -> dict[str, Any]:
        winners = loop_data.get("winners", []) or []
        variations = loop_data.get("generated_variations", []) or []
        top = winners[0] if winners else {}
        return self.brain.review_before_campaign({
            "product_name": product_name,
            "niche": niche,
            "campaign_stage": "V4",
            "budget_brl": 25,
            "metrics": {
                "connect_rate": top.get("avg_connect_rate"),
                "roas": top.get("avg_roas"),
                "purchase_rate": 2 if variations else 0,
            },
            "copy": variations[0].get("copy_text") if variations else "",
            "offer": "Variações V4/V5/V6 geradas por LearningLoop",
        })
