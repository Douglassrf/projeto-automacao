from __future__ import annotations

import json
import threading
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from app.core.config import get_settings, safe_project_path
from app.schemas.learning_loop import (
    CapiEventResult,
    CapiIngestRequest,
    CapiIngestResponse,
    GeneratedVariation,
    LearningLoopRequest,
    LearningLoopResponse,
    WinnerInsight,
)
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.decision_feed_store import DecisionFeedStore
from app.services.observability import audit_event, log_event

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / "logs"
CAPI_LOG = LOG_DIR / "capi_events.log"
LEARNING_LOG = LOG_DIR / "learning_loop.log"
_LOCK = threading.Lock()


class CapiLearningLoopService:
    """Fecha o círculo: conversão CAPI -> aprendizado -> variações V4/V5/V6.

    A primeira implementação é local e segura: grava eventos em JSONL e só encaminha
    para a Meta quando CAPI_FORWARD_ENABLED=true e as credenciais estiverem prontas.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.brain = CampaignBrainAgent()
        self.memory = CampaignMemoryStore()
        self.decision_feed = DecisionFeedStore()
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def ingest_capi_events(self, payload: CapiIngestRequest) -> CapiIngestResponse:
        results: list[CapiEventResult] = []
        stored = 0
        forwarded = 0
        for event in payload.events:
            record = event.model_dump(mode="json")
            record["received_at"] = datetime.now(UTC).isoformat()
            record["source"] = "capi_ingest"
            self._append_jsonl(CAPI_LOG, record)
            stored += 1
            did_forward = False
            message = "Evento armazenado localmente para aprendizado."
            if payload.forward_to_meta:
                if self._can_forward_to_meta():
                    # Placeholder seguro: em produção real, esta chamada vai para /{pixel_id}/events.
                    did_forward = True
                    forwarded += 1
                    message = "Evento armazenado e marcado para envio CAPI real."
                else:
                    message = "Evento armazenado; CAPI real bloqueada por credenciais/feature flag."
            results.append(CapiEventResult(event_id=event.event_id, status="ok", stored=True, forwarded_to_meta=did_forward, message=message))
        return CapiIngestResponse(received=len(payload.events), stored=stored, forwarded=forwarded, results=results)

    def run_learning_loop(self, payload: LearningLoopRequest) -> LearningLoopResponse:
        events = [e for e in self._read_events() if e.get("product_name", "").lower() == payload.product_name.lower()]
        warnings: list[str] = []
        if not events:
            warnings.append("Nenhuma conversão CAPI encontrada para este produto. Rode campanhas pequenas antes de gerar V4/V5/V6.")
            response = LearningLoopResponse(
                product_name=payload.product_name,
                analyzed_at=datetime.now(UTC),
                capi_stable=False,
                total_events_used=0,
                winners=[],
                generated_variations=[],
                next_actions=["Estabilizar CAPI e coletar pelo menos 1 compra por criativo antes de otimizar."],
                warnings=warnings,
            )
            self._append_jsonl(LEARNING_LOG, response.model_dump(mode="json"))
            return response

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            grouped[event.get("creative_id", "unknown")].append(event)

        winners: list[WinnerInsight] = []
        for creative_id, items in grouped.items():
            purchases = sum(int(item.get("purchase_count") or 0) for item in items)
            revenue = sum(float(item.get("value") or 0) for item in items)
            avg_roas = mean([float(item.get("roas") or 0) for item in items])
            avg_cpa = mean([float(item.get("cpa") or 0) for item in items])
            avg_connect_rate = mean([float(item.get("connect_rate") or 0) for item in items])
            if purchases < payload.min_purchases or avg_roas < payload.min_roas:
                continue
            sample = items[-1]
            winners.append(WinnerInsight(
                creative_id=creative_id,
                ad_name=sample.get("ad_name", ""),
                campaign_name=sample.get("campaign_name", ""),
                purchases=purchases,
                revenue=round(revenue, 2),
                avg_roas=round(avg_roas, 2),
                avg_cpa=round(avg_cpa, 2),
                avg_connect_rate=round(avg_connect_rate, 2),
                hook=sample.get("hook") or "Hook vencedor baseado na dor principal",
                creative_pattern=sample.get("creative_pattern") or "Criativo com prova visual e CTA direto",
                recommendation=self._winner_recommendation(avg_roas, avg_connect_rate),
            ))

        winners.sort(key=lambda item: (item.avg_roas, item.purchases, item.avg_connect_rate), reverse=True)
        winners = winners[: payload.max_winners]
        variations = self._generate_variations(payload, winners)
        output_folder = self._write_learning_output(payload, winners, variations) if variations else None
        capi_stable = len(events) >= 3 and bool(winners)
        if not capi_stable:
            warnings.append("CAPI ainda tem pouco volume. Use as variações como hipótese, não como escala agressiva.")

        next_actions = [
            "Validar V4/V5/V6 em dry-run no Meta Operator.",
            "Publicar com verba mínima antes de escalar.",
            "Manter auto-protection: CPA alto ou gasto sem compra deve pausar/notificar.",
        ]
        response = LearningLoopResponse(
            product_name=payload.product_name,
            analyzed_at=datetime.now(UTC),
            capi_stable=capi_stable,
            total_events_used=len(events),
            winners=winners,
            generated_variations=variations,
            next_actions=next_actions,
            warnings=warnings,
            output_folder=output_folder,
        )
        self._append_jsonl(LEARNING_LOG, response.model_dump(mode="json"))
        return response

    def run_real_controlled_loop(self, events_payload: CapiIngestRequest, loop_payload: LearningLoopRequest) -> dict[str, Any]:
        """Missao 30: fecha aprendizado real controlado sem envio externo."""
        mission_id = "30"
        brain_review = self.brain.review_before_campaign({
            "product_name": loop_payload.product_name,
            "niche": "learning_loop_real_controlled",
            "campaign_stage": "MISSAO_30_LEARNING_LOOP_REAL",
            "budget_brl": 0,
            "metrics": {
                "events_received": len(events_payload.events),
                "forward_to_meta_requested": events_payload.forward_to_meta,
                "min_roas": loop_payload.min_roas,
                "min_purchases": loop_payload.min_purchases,
            },
            "offer": "Learning Loop real controlado com eventos auditaveis locais.",
        })
        self.decision_feed.record_brain_decision(brain_review, context={
            "product_name": loop_payload.product_name,
            "niche": "learning_loop_real_controlled",
            "campaign_stage": "MISSAO_30_PRE_REVIEW",
        })

        safe_ingest_payload = CapiIngestRequest(events=events_payload.events, forward_to_meta=False)
        ingest_result = self.ingest_capi_events(safe_ingest_payload)
        loop_result = self.run_learning_loop(loop_payload)
        variations = [item.model_dump(mode="json") for item in loop_result.generated_variations]
        winners = [item.model_dump(mode="json") for item in loop_result.winners]
        status = "approved" if variations and ingest_result.forwarded == 0 else "attention"
        report = {
            "status": status,
            "mission_id": mission_id,
            "mode": "learning_loop_real_controlled",
            "product_name": loop_payload.product_name,
            "events_received": ingest_result.received,
            "events_stored": ingest_result.stored,
            "events_forwarded_to_meta": ingest_result.forwarded,
            "meta_real": False,
            "capi_forward_blocked": True,
            "total_events_used": loop_result.total_events_used,
            "capi_stable": loop_result.capi_stable,
            "winners": winners,
            "generated_variations": variations,
            "output_folder": loop_result.output_folder,
            "warnings": loop_result.warnings,
            "brain_review": brain_review,
            "next_action": "Missao 31 - MetaCampaignOperator Producao" if status == "approved" else "Coletar mais eventos antes de avancar",
        }
        audit_event(
            actor="Mission30",
            action="learning_loop_real_controlled_completed",
            resource_type="learning_loop",
            resource_id=loop_payload.product_name,
            status=status,
            mission_id=mission_id,
            details={
                "events_stored": ingest_result.stored,
                "events_forwarded_to_meta": ingest_result.forwarded,
                "variations": len(variations),
            },
        )
        log_event(
            "mission_30_learning_loop_real_controlled",
            status="ok" if status == "approved" else "attention",
            mission_id=mission_id,
            details={
                "product_name": loop_payload.product_name,
                "events_stored": ingest_result.stored,
                "variations": len(variations),
            },
        )
        self.memory.remember({
            "product_name": loop_payload.product_name,
            "niche": "learning_loop_real_controlled",
            "campaign_stage": "MISSAO_30_LEARNING_LOOP_REAL",
            "outcome": status.upper(),
            "lesson": "Learning Loop real controlado gerou aprendizado e variacoes sem enviar CAPI real para Meta.",
            "learning": "Antes de producao, revisar variacoes pelo Brain e manter aprovacao manual para qualquer campanha.",
            "metrics": {
                "events_stored": ingest_result.stored,
                "events_forwarded_to_meta": ingest_result.forwarded,
                "winners": len(winners),
                "variations": len(variations),
                "capi_stable": loop_result.capi_stable,
            },
            "source": "CapiLearningLoopService.run_real_controlled_loop",
            "output_folder": loop_result.output_folder,
        })
        return report

    def _generate_variations(self, payload: LearningLoopRequest, winners: list[WinnerInsight]) -> list[GeneratedVariation]:
        variations: list[GeneratedVariation] = []
        if not winners:
            return variations
        for idx, version in enumerate(payload.generate_versions):
            winner = winners[idx % len(winners)]
            variations.append(GeneratedVariation(
                version=version,
                based_on_creative_id=winner.creative_id,
                campaign_name=f"{payload.product_name} {version} — learning loop",
                hook=f"{winner.hook} — nova variação {version}",
                copy_text=(
                    f"O criativo base {winner.ad_name} gerou compras com ROAS médio {winner.avg_roas}. "
                    f"Esta variação mantém o padrão vencedor: {winner.creative_pattern}. "
                    "Clique e veja a oferta completa hoje."
                ),
                image_prompt=f"Criar imagem {version} mantendo o padrão campeão: {winner.creative_pattern}. Visual limpo, benefício direto, CTA discreto.",
                video_script=f"0-3s: {winner.hook}. 3-12s: mostrar problema. 12-22s: apresentar solução. 22-30s: CTA para compra.",
                reason=f"Baseada em criativo com {winner.purchases} compras, ROAS {winner.avg_roas} e Connect Rate {winner.avg_connect_rate}%.",
            ))
        return variations

    def _winner_recommendation(self, roas: float, connect_rate: float) -> str:
        if roas >= 3 and connect_rate >= 75:
            return "Criativo forte: gerar V4/V5/V6 e testar escala controlada."
        if connect_rate < 75:
            return "Conversão existe, mas corrigir página/carregamento antes de escalar."
        return "Criativo promissor: gerar variações e validar com orçamento mínimo."

    def _write_learning_output(self, payload: LearningLoopRequest, winners: list[WinnerInsight], variations: list[GeneratedVariation]) -> str:
        root = safe_project_path(self.settings.kit_output_dir, "data/campaign_kits") / "Learning_Loop" / payload.product_name.replace(" ", "_")
        root.mkdir(parents=True, exist_ok=True)
        data = {
            "product_name": payload.product_name,
            "generated_at": datetime.now(UTC).isoformat(),
            "winners": [w.model_dump(mode="json") for w in winners],
            "variations": [v.model_dump(mode="json") for v in variations],
        }
        (root / "learning_loop_v4_v5_v6.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        md = [f"# Learning Loop — {payload.product_name}", "", "## Criativos vencedores"]
        for winner in winners:
            md.append(f"- {winner.ad_name}: {winner.purchases} compras | ROAS {winner.avg_roas} | CPA {winner.avg_cpa}")
        md.extend(["", "## Novas variações"])
        for variation in variations:
            md.append(f"### {variation.version}\nHook: {variation.hook}\n\nCopy: {variation.copy_text}\n")
        (root / "README_LEARNING_LOOP.md").write_text("\n".join(md), encoding="utf-8")
        return str(root)

    def _read_events(self) -> list[dict[str, Any]]:
        if not CAPI_LOG.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in CAPI_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        with _LOCK:
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _can_forward_to_meta(self) -> bool:
        return bool(getattr(self.settings, "capi_enabled", False) and self.settings.meta_access_token)
