from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import project_root
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.decision_feed_store import DecisionFeedStore
from app.services.observability import audit_event, log_event


class FacebookAdMiner:
    """Coletor interno controlado de anúncios.

    Missão 06:
    - Não chama API externa.
    - Não usa Selenium.
    - Não abre navegador.
    - Não faz scraping.
    - Retorna dados simulados estruturados para o MinerEngine.
    """

    def __init__(self, repository=None, dry_run: bool = True, can_external_call: bool = False) -> None:
        self.repository = repository
        self.dry_run = dry_run
        self.can_external_call = can_external_call
        self.brain = CampaignBrainAgent()
        self.memory = CampaignMemoryStore()
        self.decision_feed = DecisionFeedStore()

    def mine(self, product_name: str = "Ebook de Receitas Fitness", niche: str = "emagrecimento", user_id: int | None = 1) -> dict[str, Any]:
        """Retorna um pacote mockado de anúncios candidatos.

        Esta função é propositalmente local e determinística.
        A função serve para validar o fluxo:

        FacebookAdMiner -> MinerEngine -> AdProcessor -> CampaignBrainAgent
        """
        ads = [
            {
                "source": "mock_facebook_ad_library",
                "ad_id": "mock_ad_001",
                "product_name": product_name,
                "niche": niche,
                "creative_angle": "receitas fitness rápidas",
                "hook": "Coma melhor sem perder tempo",
                "active_ads": 22,
                "cpc": 1.35,
                "link_clicks": 1000,
                "landing_page_views": 820,
                "checkout_starts": 210,
                "purchases": 28,
                "country": "BR",
                "language": "pt-BR",
                "risk_notes": ["nicho sensível: emagrecimento", "evitar promessas milagrosas"],
            },
            {
                "source": "mock_facebook_ad_library",
                "ad_id": "mock_ad_002",
                "product_name": f"{product_name} - Variação",
                "niche": niche,
                "creative_angle": "planejamento alimentar simples",
                "hook": "Organize sua alimentação em poucos minutos",
                "active_ads": 16,
                "cpc": 1.10,
                "link_clicks": 700,
                "landing_page_views": 520,
                "checkout_starts": 90,
                "purchases": 9,
                "country": "BR",
                "language": "pt-BR",
                "risk_notes": ["revisar prova social", "validar promessa da página"],
            },
        ]

        package = {
            "status": "ok",
            "agent": "FacebookAdMiner",
            "mode": "controlado_mock",
            "dry_run": self.dry_run,
            "can_external_call": self.can_external_call,
            "external_calls_made": 0,
            "scraping_used": False,
            "selenium_used": False,
            "browser_used": False,
            "user_id": user_id,
            "product_name": product_name,
            "niche": niche,
            "collected_at": datetime.now(UTC).isoformat(),
            "ads_count": len(ads),
            "ads": ads,
        }

        if self.repository and hasattr(self.repository, "save_mining_package"):
            return self.repository.save_mining_package(package)

        return package

    def best_candidate(self, mining_package: dict[str, Any]) -> dict[str, Any]:
        """Escolhe o melhor candidato mockado com base em compras e volume.

        Não é uma decisão final de campanha. É apenas seleção inicial para
        alimentar MinerEngine/AdProcessor.
        """
        ads = mining_package.get("ads") or []
        if not ads:
            return {}
        return sorted(
            ads,
            key=lambda item: (
                int(item.get("purchases") or 0),
                int(item.get("active_ads") or 0),
                int(item.get("landing_page_views") or 0),
            ),
            reverse=True,
        )[0]

    def controlled_real_collect(
        self,
        *,
        product_name: str,
        niche: str,
        local_export_ads: list[dict[str, Any]] | None = None,
        max_ads: int = 20,
        source_label: str = "local_ad_library_export",
        allow_external_call: bool = False,
        use_browser: bool = False,
        use_selenium: bool = False,
        source_url: str | None = None,
        user_id: int | None = 1,
    ) -> dict[str, Any]:
        """Missao 29: coleta real controlada por export local auditavel.

        Ainda nao faz scraping nem chama Meta/Facebook. A fronteira real aqui e
        aceitar dados exportados localmente e rastrear todos os guardrails.
        """
        started = time.perf_counter()
        mission_id = "29"
        run_id = f"fbminer29_{uuid4().hex[:10]}"
        pre_review = self.brain.review_before_campaign({
            "product_name": product_name,
            "niche": niche,
            "campaign_stage": "MISSAO_29_FACEBOOK_AD_MINER_REAL",
            "budget_brl": 0,
            "metrics": {
                "ads_received": len(local_export_ads or []),
                "max_ads": max_ads,
                "allow_external_call": allow_external_call,
                "use_browser": use_browser,
                "use_selenium": use_selenium,
                "source_url_provided": bool(source_url),
            },
            "offer": "FacebookAdMiner real controlado com export local auditavel.",
        })
        self.decision_feed.record_brain_decision(pre_review, context={
            "product_name": product_name,
            "niche": niche,
            "campaign_stage": "MISSAO_29_PRE_REVIEW",
        })

        blocked_reasons = []
        if allow_external_call or self.can_external_call:
            blocked_reasons.append("external_call_blocked")
        if use_browser:
            blocked_reasons.append("browser_blocked")
        if use_selenium:
            blocked_reasons.append("selenium_blocked")
        if source_url:
            blocked_reasons.append("source_url_blocked_until_manual_approval")

        if blocked_reasons:
            result = {
                "status": "blocked",
                "run_id": run_id,
                "mission_id": mission_id,
                "agent": "FacebookAdMiner",
                "mode": "controlled_real_local_export",
                "blocked_reasons": blocked_reasons,
                "external_calls_made": 0,
                "scraping_used": False,
                "browser_used": False,
                "selenium_used": False,
                "meta_real": False,
                "brain_review": pre_review,
            }
            self._record_mission29_learning(result, product_name, niche)
            return result

        raw_ads = local_export_ads if local_export_ads is not None else self.mine(product_name=product_name, niche=niche, user_id=user_id).get("ads", [])
        limited_ads = raw_ads[: max(1, min(max_ads, 100))]
        normalized_ads = [self._normalize_export_ad(ad, product_name, niche) for ad in limited_ads]
        candidate = self.best_candidate({"ads": normalized_ads})
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        result = {
            "status": "approved" if normalized_ads else "attention",
            "run_id": run_id,
            "mission_id": mission_id,
            "agent": "FacebookAdMiner",
            "mode": "controlled_real_local_export",
            "source_label": source_label,
            "dry_run": True,
            "product_name": product_name,
            "niche": niche,
            "collected_at": datetime.now(UTC).isoformat(),
            "ads_received": len(raw_ads),
            "ads_collected": len(normalized_ads),
            "max_ads": max_ads,
            "external_calls_made": 0,
            "scraping_used": False,
            "browser_used": False,
            "selenium_used": False,
            "meta_real": False,
            "ads": normalized_ads,
            "selected_candidate": candidate,
            "latency_ms": latency_ms,
            "brain_review": pre_review,
            "next_action": "Missao 30 - Learning Loop Real" if normalized_ads else "Fornecer export local valido antes de avancar",
        }
        report_path = self._write_mission29_report(result)
        result["report_path"] = str(report_path)
        audit_event(
            actor="Mission29",
            action="facebook_ad_miner_controlled_real_completed",
            resource_type="facebook_ad_miner",
            resource_id=report_path.name,
            status=result["status"],
            mission_id=mission_id,
            details={
                "ads_collected": len(normalized_ads),
                "external_calls_made": 0,
                "blocked_reasons": [],
            },
        )
        log_event(
            "mission_29_facebook_ad_miner_controlled_real",
            status="ok" if result["status"] == "approved" else "attention",
            latency_ms=latency_ms,
            mission_id=mission_id,
            details={
                "run_id": run_id,
                "ads_collected": len(normalized_ads),
                "report_path": str(report_path),
            },
        )
        self._record_mission29_learning(result, product_name, niche)
        if self.repository and hasattr(self.repository, "save_mining_package"):
            self.repository.save_mining_package(result)
        return result

    def _normalize_export_ad(self, ad: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        return {
            "source": str(ad.get("source") or "local_ad_library_export"),
            "ad_id": str(ad.get("ad_id") or f"local_{uuid4().hex[:8]}"),
            "product_name": str(ad.get("product_name") or product_name),
            "niche": str(ad.get("niche") or niche),
            "creative_angle": str(ad.get("creative_angle") or ""),
            "hook": str(ad.get("hook") or ""),
            "active_ads": int(ad.get("active_ads") or 0),
            "cpc": float(ad.get("cpc") or 0),
            "link_clicks": int(ad.get("link_clicks") or 0),
            "landing_page_views": int(ad.get("landing_page_views") or 0),
            "checkout_starts": int(ad.get("checkout_starts") or 0),
            "purchases": int(ad.get("purchases") or 0),
            "country": str(ad.get("country") or "unknown"),
            "language": str(ad.get("language") or "unknown"),
            "risk_notes": list(ad.get("risk_notes") or []),
        }

    def _write_mission29_report(self, report: dict[str, Any]) -> Path:
        reports_dir = project_root() / "logs" / "facebook_ad_miner"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"{report['run_id']}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _record_mission29_learning(self, result: dict[str, Any], product_name: str, niche: str) -> None:
        self.memory.remember({
            "product_name": product_name,
            "niche": niche,
            "campaign_stage": "MISSAO_29_FACEBOOK_AD_MINER_REAL",
            "outcome": str(result.get("status", "unknown")).upper(),
            "lesson": "FacebookAdMiner real controlado aceita export local auditavel e bloqueia rede, browser, Selenium, scraping e Meta real.",
            "learning": "Para avancar ao Learning Loop real, usar anuncios coletados com origem auditavel e manter rastreabilidade completa.",
            "metrics": {
                "ads_collected": result.get("ads_collected", 0),
                "external_calls_made": result.get("external_calls_made", 0),
                "scraping_used": result.get("scraping_used", False),
                "browser_used": result.get("browser_used", False),
                "selenium_used": result.get("selenium_used", False),
                "blocked_reasons": result.get("blocked_reasons", []),
            },
            "source": "FacebookAdMiner.controlled_real_collect",
            "output_file": result.get("report_path"),
        })
