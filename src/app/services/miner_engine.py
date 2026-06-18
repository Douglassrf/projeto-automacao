import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import project_root
from app.schemas.ads import AdAnalysisRequest
from app.services.ad_processor import AdProcessor
from app.services.facebook_ad_miner import FacebookAdMiner
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.decision_feed_store import DecisionFeedStore
from app.services.observability import audit_event, log_event


class MinerEngine:
    """Motor interno para orquestrar mineração, análise e cérebro consultivo.

    Fase 6:
    - Usa FacebookAdMiner controlado.
    - Não usa API externa.
    - Não usa scraping.
    - Não depende de legacy.py.
    - Usa AdProcessor como cérebro de análise métrica.
    - Usa CampaignBrainAgent como cérebro estratégico consultivo.
    """

    def __init__(self, repository):
        self.repository = repository
        self.processor = AdProcessor(repository=repository)
        self.facebook_miner = FacebookAdMiner(repository=repository)
        self.brain = CampaignBrainAgent()
        self.memory = CampaignMemoryStore()
        self.decision_feed = DecisionFeedStore()

    def analyze(self, payload: AdAnalysisRequest, user_id: int | None = None) -> dict:
        result = self.processor.process(payload, user_id=user_id)
        brain_review = self.brain.review_before_campaign({
            "product_name": payload.product_name,
            "niche": "emagrecimento",
            "campaign_stage": "V1",
            "budget_brl": 25,
            "metrics": {
                "connect_rate": result.get("connect_rate"),
                "checkout_rate": result.get("checkout_rate"),
                "purchase_rate": result.get("purchase_rate"),
            },
        })
        return {
            "status": "ok",
            "fase": "fase_6",
            "modo": "facebook_ad_miner_controlado",
            "resultado": result,
            "brain_review": brain_review,
        }

    def analyze_mock(self) -> dict:
        mining_package = self.facebook_miner.mine(
            product_name="Ebook de Receitas Fitness",
            niche="emagrecimento",
            user_id=1,
        )
        candidate = self.facebook_miner.best_candidate(mining_package)

        payload = AdAnalysisRequest(
            user_id=1,
            product_name=candidate.get("product_name", "Ebook de Receitas Fitness"),
            active_ads=int(candidate.get("active_ads") or 0),
            cpc=float(candidate.get("cpc") or 0),
            link_clicks=int(candidate.get("link_clicks") or 0),
            landing_page_views=int(candidate.get("landing_page_views") or 0),
            checkout_starts=int(candidate.get("checkout_starts") or 0),
            purchases=int(candidate.get("purchases") or 0),
        )

        analysis = self.analyze(payload, user_id=payload.user_id)
        analysis["mining_package"] = {
            "agent": mining_package.get("agent"),
            "mode": mining_package.get("mode"),
            "dry_run": mining_package.get("dry_run"),
            "external_calls_made": mining_package.get("external_calls_made"),
            "scraping_used": mining_package.get("scraping_used"),
            "selenium_used": mining_package.get("selenium_used"),
            "browser_used": mining_package.get("browser_used"),
            "ads_count": mining_package.get("ads_count"),
        }
        analysis["selected_candidate"] = candidate
        return analysis

    def controlled_real_mine(
        self,
        *,
        product_name: str,
        niche: str,
        ads: list[dict[str, Any]] | None = None,
        max_ads: int = 10,
        allow_external_call: bool = False,
        source_label: str = "local_payload",
        user_id: int | None = 1,
    ) -> dict[str, Any]:
        """Missao 28: mineracao real controlada por fonte local auditavel.

        O motor processa dados reais fornecidos localmente, mas mantem bloqueados:
        rede, scraping, navegador, Selenium, Meta real e qualquer provider externo.
        """
        started = time.perf_counter()
        run_id = f"miner28_{uuid4().hex[:10]}"
        mission_id = "28"

        pre_review = self.brain.review_before_campaign({
            "product_name": product_name,
            "niche": niche,
            "campaign_stage": "MISSAO_28_MINER_CONTROLLED_REAL",
            "budget_brl": 0,
            "metrics": {
                "max_ads": max_ads,
                "ads_received": len(ads or []),
                "allow_external_call": allow_external_call,
            },
            "offer": "MinerEngine real controlado com fonte local auditavel.",
        })
        self.decision_feed.record_brain_decision(pre_review, context={
            "product_name": product_name,
            "niche": niche,
            "campaign_stage": "MISSAO_28_PRE_REVIEW",
        })

        if allow_external_call:
            result = {
                "status": "blocked",
                "run_id": run_id,
                "mission_id": mission_id,
                "reason": "External calls remain blocked in Mission 28.",
                "external_calls_made": 0,
                "scraping_used": False,
                "browser_used": False,
                "selenium_used": False,
                "brain_review": pre_review,
            }
            self._record_mission28_learning(result, product_name, niche)
            return result

        source_ads = ads if ads is not None else self._default_controlled_ads(product_name, niche)
        limited_ads = source_ads[: max(1, min(max_ads, 50))]
        analyses: list[dict[str, Any]] = []
        for index, ad in enumerate(limited_ads, start=1):
            payload = self._ad_to_payload(ad, product_name=product_name, user_id=user_id)
            analysis = self.analyze(payload, user_id=user_id)
            analyses.append({
                "rank_input": index,
                "source_ad": ad,
                "analysis": analysis.get("resultado", {}),
                "brain_review": analysis.get("brain_review", {}),
            })

        ranked = sorted(
            analyses,
            key=lambda item: (
                float(item["analysis"].get("score") or 0),
                int(item["analysis"].get("purchases") or 0),
                int(item["analysis"].get("active_ads") or 0),
            ),
            reverse=True,
        )
        best = ranked[0] if ranked else None
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        report = {
            "status": "approved" if ranked else "attention",
            "run_id": run_id,
            "mission_id": mission_id,
            "mode": "controlled_real_local_source",
            "source_label": source_label,
            "product_name": product_name,
            "niche": niche,
            "started_at": datetime.now(UTC).isoformat(),
            "latency_ms": latency_ms,
            "ads_received": len(source_ads),
            "ads_processed": len(limited_ads),
            "max_ads": max_ads,
            "external_calls_made": 0,
            "scraping_used": False,
            "browser_used": False,
            "selenium_used": False,
            "meta_real": False,
            "selected_candidate": best,
            "ranked_candidates": ranked,
            "brain_review": pre_review,
            "next_action": "Missao 29 - FacebookAdMiner Real" if ranked else "Coletar fonte local valida antes de avancar",
        }
        report_path = self._write_mission28_report(report)
        report["report_path"] = str(report_path)
        audit_event(
            actor="Mission28",
            action="controlled_real_miner_completed",
            resource_type="miner_engine",
            resource_id=report_path.name,
            status=report["status"],
            mission_id=mission_id,
            details={
                "ads_processed": len(limited_ads),
                "external_calls_made": 0,
                "latency_ms": latency_ms,
            },
        )
        log_event(
            "mission_28_miner_controlled_real",
            status="ok" if report["status"] == "approved" else "attention",
            latency_ms=latency_ms,
            mission_id=mission_id,
            details={
                "run_id": run_id,
                "ads_processed": len(limited_ads),
                "report_path": str(report_path),
            },
        )
        self._record_mission28_learning(report, product_name, niche)
        return report

    def _ad_to_payload(self, ad: dict[str, Any], *, product_name: str, user_id: int | None) -> AdAnalysisRequest:
        return AdAnalysisRequest(
            user_id=user_id,
            product_name=str(ad.get("product_name") or product_name),
            active_ads=int(ad.get("active_ads") or 0),
            cpc=float(ad.get("cpc") or 0),
            link_clicks=int(ad.get("link_clicks") or 0),
            landing_page_views=int(ad.get("landing_page_views") or 0),
            checkout_starts=int(ad.get("checkout_starts") or 0),
            purchases=int(ad.get("purchases") or 0),
        )

    def _default_controlled_ads(self, product_name: str, niche: str) -> list[dict[str, Any]]:
        package = self.facebook_miner.mine(product_name=product_name, niche=niche, user_id=1)
        return list(package.get("ads") or [])

    def _write_mission28_report(self, report: dict[str, Any]) -> Path:
        reports_dir = project_root() / "logs" / "miner_controlled"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"{report['run_id']}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _record_mission28_learning(self, result: dict[str, Any], product_name: str, niche: str) -> None:
        self.memory.remember({
            "product_name": product_name,
            "niche": niche,
            "campaign_stage": "MISSAO_28_MINER_CONTROLLED_REAL",
            "outcome": str(result.get("status", "unknown")).upper(),
            "lesson": "MinerEngine executou mineracao real controlada somente com fonte local auditavel e sem chamadas externas.",
            "learning": "Para avancar para FacebookAdMiner real, manter limites, auditoria, rollback e bloqueio de producao real.",
            "metrics": {
                "ads_processed": result.get("ads_processed", 0),
                "external_calls_made": result.get("external_calls_made", 0),
                "scraping_used": result.get("scraping_used", False),
                "latency_ms": result.get("latency_ms"),
            },
            "source": "MinerEngine.controlled_real_mine",
            "output_file": result.get("report_path"),
        })
