from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.campaign_memory import CampaignMemoryStore
from app.services.campaign_intelligence_safe import CampaignIntelligenceSafe
from app.services.decision_feed_store import DecisionFeedStore
from app.services.meta_update_watcher import MetaUpdateWatcher


class CampaignBrainAgent:
    """Cérebro estratégico consultivo e memória evolutiva inicial.

    Modo seguro:
    - read_only=True para execução de campanhas.
    - dry_run=True.
    - can_execute=False.

    Este agente não publica campanha, não altera orçamento, não chama API externa
    e não aciona MetaCampaignOperator, VideoPipeline ou PremiumRender.
    Ele lê memórias, avalia risco, recomenda e registra aprendizado apenas
    quando chamado explicitamente pelo endpoint de aprendizado.
    """

    SENSITIVE_NICHES = {
        "emagrecimento",
        "saude",
        "saúde",
        "fitness",
        "cripto",
        "crypto",
        "investimento",
        "financeiro",
        "apostas",
        "bet",
        "remedio",
        "remédio",
        "suplemento",
    }

    STAGE_MATRIX = {
        "V1": {
            "goal": "descoberta",
            "default_budget_brl": 25,
            "next_if_positive": "V2",
            "main_metrics": ["ctr", "cpc", "connect_rate"],
        },
        "V2": {
            "goal": "validação",
            "default_budget_brl": 50,
            "next_if_positive": "V3",
            "main_metrics": ["connect_rate", "checkout_rate", "purchase_rate"],
        },
        "V3": {
            "goal": "selecionar campeão",
            "default_budget_brl": 50,
            "next_if_positive": "V4",
            "main_metrics": ["purchase_rate", "cpa", "roas", "connect_rate"],
        },
        "V4": {
            "goal": "escala controlada",
            "default_budget_brl": 100,
            "next_if_positive": "V5",
            "main_metrics": ["cpa", "roas", "spend", "purchases"],
        },
        "V5": {
            "goal": "otimização inteligente",
            "default_budget_brl": 150,
            "next_if_positive": "V6",
            "main_metrics": ["bottleneck", "creative_pattern", "offer", "checkout_rate"],
        },
        "V6": {
            "goal": "dominação",
            "default_budget_brl": 200,
            "next_if_positive": "scale",
            "main_metrics": ["roas", "profit", "creative_winners", "geo_expansion"],
        },
    }

    def __init__(
        self,
        knowledge_dir: Path | None = None,
        logs_dir: Path | None = None,
        read_only: bool = True,
        dry_run: bool = True,
        can_execute: bool = False,
    ) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.knowledge_dir = knowledge_dir or project_root / "src" / "knowledge"
        self.logs_dir = logs_dir or project_root / "logs"
        self.read_only = read_only
        self.dry_run = dry_run
        self.can_execute = can_execute
        self.memory_store = CampaignMemoryStore(logs_dir=self.logs_dir)
        self.campaign_intelligence = CampaignIntelligenceSafe(logs_dir=self.logs_dir)
        self.decision_feed = DecisionFeedStore(logs_dir=self.logs_dir)
        self.meta_update_watcher = MetaUpdateWatcher(logs_dir=self.logs_dir)

    def review_before_campaign(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Revisa uma campanha antes de qualquer execução."""
        context = context or {}
        product_name = str(context.get("product_name") or "Produto sem nome")
        niche = str(context.get("niche") or context.get("nicho") or "").lower()
        stage = str(context.get("campaign_stage") or context.get("stage") or "V1").upper()
        budget = float(context.get("budget_brl") or context.get("budget") or self.STAGE_MATRIX.get(stage, {}).get("default_budget_brl", 25))

        knowledge_summary = self._knowledge_summary()
        learning_summary = self._learning_summary()
        experience_summary = self.memory_store.summarize(product_name=product_name, niche=niche)
        intelligence_summary = self.campaign_intelligence.analyze(product_name=product_name, niche=niche)
        meta_update_assessment = self.meta_update_watcher.assess_context(context)
        metrics = context.get("metrics") or {}
        policy_risk = self._policy_risk(product_name=product_name, niche=niche, context=context)
        stage_info = self.STAGE_MATRIX.get(stage, self.STAGE_MATRIX["V1"])

        positives: list[str] = []
        negatives: list[str] = []
        blocked_reasons: list[str] = []

        positives.append("CampaignBrainAgent em modo consultivo seguro: read_only, dry_run e sem execução automática.")
        positives.append(f"Etapa {stage} reconhecida como {stage_info['goal']}.")
        positives.append(f"Orçamento de referência da etapa: R$ {stage_info['default_budget_brl']}.")

        if experience_summary["available"]:
            positives.append(f"Memória evolutiva consultada: {experience_summary['total_records']} registros totais.")
            if experience_summary["similar_records"]:
                positives.append(f"Foram encontrados {experience_summary['similar_records']} registros parecidos na memória.")
        else:
            negatives.append("Memória evolutiva local ainda sem registros; manter operação conservadora.")

        if stage == "V1" and budget <= 25:
            positives.append("Teste inicial respeita a estratégia de descoberta com orçamento controlado de até R$ 25.")
        elif stage == "V1" and budget > 25:
            negatives.append("Orçamento acima de R$ 25 para V1; recomenda-se reduzir para teste inicial.")
            blocked_reasons.append("budget_above_v1_limit")

        connect_rate = self._number(metrics.get("connect_rate"))
        checkout_rate = self._number(metrics.get("checkout_rate"))
        purchase_rate = self._number(metrics.get("purchase_rate"))
        roas = self._number(metrics.get("roas"))

        if connect_rate is not None:
            if connect_rate >= 75:
                positives.append("Connect Rate saudável para análise inicial.")
            else:
                negatives.append("Connect Rate abaixo de 75%; revisar página, domínio, velocidade ou rastreamento.")
        if checkout_rate is not None:
            if checkout_rate >= 20:
                positives.append("Checkout Rate com sinal mínimo aceitável.")
            else:
                negatives.append("Checkout Rate abaixo de 20%; revisar promessa, preço, prova e CTA.")
        if purchase_rate is not None:
            if purchase_rate >= 2:
                positives.append("Purchase Rate com bom sinal inicial.")
            else:
                negatives.append("Purchase Rate ainda baixo; não escalar sem mais validação.")
        if roas is not None:
            if roas > 1:
                positives.append("ROAS positivo informado no contexto.")
            else:
                negatives.append("ROAS informado ainda não sustenta escala.")

        if policy_risk["level"] == "alto":
            negatives.append("Nicho/produto possui risco alto de política Meta; campanha deve ficar bloqueada até revisão.")
            blocked_reasons.append("high_meta_policy_risk")
        elif policy_risk["level"] == "medio":
            negatives.append("Nicho/produto sensível; exigir revisão de copy, criativo, página e promessa.")
        else:
            positives.append("Nenhum risco crítico de política Meta identificado pela análise local.")

        if meta_update_assessment.get("highest_risk") == "high":
            negatives.append("MetaUpdateWatcher encontrou atualização relacionada de alto risco.")
            blocked_reasons.append("meta_update_high_risk")
        elif meta_update_assessment.get("highest_risk") == "medium":
            negatives.append("MetaUpdateWatcher encontrou atualização relacionada de risco médio; revisar antes de publicar.")
        else:
            positives.append("MetaUpdateWatcher não encontrou atualização crítica relacionada.")

        if intelligence_summary.get("source_counts", {}).get("decision_feed_matched", 0) or intelligence_summary.get("source_counts", {}).get("campaign_memory_matched", 0):
            positives.append("CampaignIntelligence encontrou dados comparativos para este contexto.")
        if intelligence_summary.get("winners", 0) > intelligence_summary.get("losers", 0):
            positives.append("Campanha comparativa encontrou mais sinais vencedores do que perdedores.")
        elif intelligence_summary.get("losers", 0) > intelligence_summary.get("winners", 0):
            negatives.append("Campanha comparativa encontrou mais sinais perdedores do que vencedores.")

        if experience_summary.get("blocked"):
            negatives.append("Há bloqueios anteriores parecidos na memória evolutiva.")
        if experience_summary.get("losers") and not experience_summary.get("winners"):
            negatives.append("Histórico parecido majoritariamente negativo; exigir revisão antes de avançar.")
        if experience_summary.get("winners"):
            positives.append("Memória encontrou sinais vencedores anteriores relacionados.")

        if not knowledge_summary["available"]:
            negatives.append("Memória de regras não encontrada; revisar pasta src/knowledge antes de aprovar campanha.")
            blocked_reasons.append("knowledge_memory_missing")

        can_recommend = not blocked_reasons
        decision = "SIM" if can_recommend else "NÃO"
        confidence = self._confidence(positives, negatives, blocked_reasons)
        next_action = "dry_run" if can_recommend else "bloquear_e_revisar"

        response = {
            "agent": "CampaignBrainAgent",
            "status": "ok",
            "mode": "consultivo_read_only_memoria_evolutiva",
            "read_only": self.read_only,
            "dry_run": self.dry_run,
            "can_execute": self.can_execute,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "decision": decision,
            "confidence": confidence,
            "campaign_stage": stage,
            "stage_goal": stage_info["goal"],
            "recommended_budget_brl": stage_info["default_budget_brl"],
            "positive_points": positives,
            "negative_points": negatives,
            "panoramic_view": self._panoramic_view(decision, stage, policy_risk, positives, negatives, experience_summary),
            "recommended_solution": self._recommended_solution(decision, stage, blocked_reasons, experience_summary),
            "experience_summary": experience_summary,
            "campaign_intelligence": intelligence_summary,
            "intelligence_recommendation": intelligence_summary.get("recommendation"),
            "historical_recommendation": experience_summary["historical_recommendation"],
            "memory_used": {
                "rules": knowledge_summary,
                "experience": experience_summary,
                "comparative_intelligence": intelligence_summary,
                "creatives": learning_summary,
                "blocks": {"source": "performance_tickets/meta_action_requests/decision_logs", "available": "requires_database_runtime"},
                "meta_updates": meta_update_assessment,
            },
            "meta_risk": policy_risk,
            "blocked_reasons": blocked_reasons,
            "next_action": next_action,
        }
        response["decision_feed_result"] = self.decision_feed.record_brain_decision(
            response,
            context={
                "product_name": product_name,
                "niche": niche,
                "campaign_stage": stage,
                "budget_brl": budget,
            },
        )
        return response

    def learn_after_campaign(self, result: dict[str, Any] | None = None) -> dict[str, Any]:
        """Registra aprendizado local controlado.

        Esta ação grava apenas em JSONL local, não aciona Meta, não altera campanha
        e não chama outros agentes executores.
        """
        result = result or {}
        record = {
            "product_name": result.get("product_name") or "Produto sem nome",
            "niche": result.get("niche") or result.get("nicho") or "",
            "campaign_stage": result.get("campaign_stage") or result.get("stage") or "V1",
            "outcome": result.get("outcome") or result.get("decision") or "UNKNOWN",
            "lesson": result.get("lesson") or result.get("learning") or "Aprendizado registrado sem lição detalhada.",
            "metrics": result.get("metrics") or {},
            "source": "CampaignBrainAgent.learn_after_campaign",
        }
        stored = self.memory_store.remember(record)
        return {
            "agent": "CampaignBrainAgent",
            "status": "ok",
            "mode": "memoria_evolutiva_local",
            "read_only_execution": self.read_only,
            "message": "Aprendizado registrado em memória local JSONL. Nenhuma campanha foi executada.",
            "stored": stored,
            "record": record,
        }

    def _knowledge_summary(self) -> dict[str, Any]:
        files: list[str] = []
        keys: dict[str, list[str]] = {}
        if self.knowledge_dir.exists():
            for path in sorted(self.knowledge_dir.glob("*.json")):
                files.append(path.name)
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        keys[path.name] = sorted(list(data.keys()))[:12]
                except Exception as exc:
                    keys[path.name] = [f"erro_leitura: {type(exc).__name__}"]
        return {
            "source": str(self.knowledge_dir),
            "available": bool(files),
            "files_count": len(files),
            "files": files[:20],
            "top_keys": keys,
        }

    def _learning_summary(self) -> dict[str, Any]:
        capi = self.logs_dir / "capi_events.log"
        learning = self.logs_dir / "learning_loop.log"
        return {
            "source": str(self.logs_dir),
            "available": capi.exists() or learning.exists(),
            "files": {
                "capi_events.log": capi.exists(),
                "learning_loop.log": learning.exists(),
            },
        }

    def _policy_risk(self, product_name: str, niche: str, context: dict[str, Any]) -> dict[str, Any]:
        text = " ".join([
            product_name.lower(),
            niche.lower(),
            str(context.get("offer") or "").lower(),
            str(context.get("copy") or "").lower(),
        ])
        hits = sorted([item for item in self.SENSITIVE_NICHES if item in text])
        if any(item in hits for item in ["emagrecimento", "saude", "saúde", "cripto", "crypto", "apostas", "bet", "remedio", "remédio"]):
            level = "medio"
        else:
            level = "baixo"
        risky_promises = ["garantido", "milagroso", "cura", "100%", "sem esforço", "enriqueça rápido"]
        promise_hits = [term for term in risky_promises if term in text]
        if promise_hits:
            level = "alto"
        return {
            "level": level,
            "sensitive_terms": hits,
            "risky_promises": promise_hits,
            "note": "Análise local preliminar. Validar com MetaUpdateWatcher e padrões oficiais antes de publicação real.",
        }

    def _confidence(self, positives: list[str], negatives: list[str], blocked_reasons: list[str]) -> int:
        score = 60 + (len(positives) * 4) - (len(negatives) * 7) - (len(blocked_reasons) * 15)
        return max(0, min(100, score))

    def _panoramic_view(self, decision: str, stage: str, policy_risk: dict[str, Any], positives: list[str], negatives: list[str], experience: dict[str, Any]) -> str:
        memory_note = f" Memória parecida: {experience.get('similar_records', 0)} registros."
        if decision == "SIM":
            return (
                f"A campanha pode seguir apenas em modo dry_run/validação controlada na etapa {stage}. "
                f"Foram encontrados {len(positives)} sinais positivos e {len(negatives)} pontos de atenção. "
                f"Risco Meta preliminar: {policy_risk['level']}."
                f"{memory_note}"
            )
        return (
            f"A campanha não deve avançar agora. Etapa {stage} exige revisão antes de qualquer execução. "
            f"Foram encontrados {len(negatives)} pontos de atenção e risco Meta preliminar {policy_risk['level']}."
            f"{memory_note}"
        )

    def _recommended_solution(self, decision: str, stage: str, blocked_reasons: list[str], experience: dict[str, Any]) -> str:
        if "budget_above_v1_limit" in blocked_reasons:
            return "Reduzir orçamento da V1 para R$ 25 e repetir a revisão do cérebro."
        if "high_meta_policy_risk" in blocked_reasons:
            return "Revisar copy, promessa, criativo e página antes de qualquer campanha."
        if "knowledge_memory_missing" in blocked_reasons:
            return "Restaurar/validar src/knowledge/*.json antes de aprovar campanha."
        if "meta_update_high_risk" in blocked_reasons:
            return "Bloquear publicação real e revisar atualização da Meta antes de qualquer campanha."
        if experience.get("blocked"):
            return "Investigar bloqueios anteriores antes de dry_run."
        if decision == "SIM":
            return (
                "Prosseguir somente com dry_run e orçamento controlado. "
                "Registrar a decisão, observar métricas e alimentar a memória evolutiva após o teste."
            )
        return "Bloquear e revisar dados mínimos da campanha antes de avançar."

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
