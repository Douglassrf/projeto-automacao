from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.site_builder import SiteGenerateRequest
from app.services.campaign_brain import CampaignBrainAgent
from app.services.campaign_memory import CampaignMemoryStore
from app.services.decision_feed_store import DecisionFeedStore


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._ -]", "", value).strip().lower()
    value = re.sub(r"\s+", "-", value)
    return value[:80] or "site"


class SiteBuilderBridge:
    """Camada segura do SiteBuilder.

    Missão 23:
    - Não executa deploy real.
    - Não chama GitHub/Vercel/Netlify.
    - Usa output local dentro do projeto.
    - Gera index.html, styles.css, deploy_payload.json e manifest.
    - Registra memória, DecisionFeed e Brain.
    """

    def __init__(self, logs_dir: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        self.project_root = project_root
        self.logs_dir = logs_dir or project_root / "logs"
        self.output_root = project_root / "data" / "campaign_kits" / "SiteBuilderSafe"
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.decision_feed = DecisionFeedStore(logs_dir=self.logs_dir)
        self.memory = CampaignMemoryStore(logs_dir=self.logs_dir)
        self.brain = CampaignBrainAgent(logs_dir=self.logs_dir)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "agent": "SiteBuilderBridge",
            "mode": "site_builder_safe",
            "deploy_real_enabled": False,
            "github_enabled": False,
            "vercel_enabled": False,
            "netlify_enabled": False,
            "meta_real": False,
            "tiktok_real": False,
            "output_root": str(self.output_root),
        }

    def run_mock_cycle(self) -> dict[str, Any]:
        from app.schemas.site_builder import SiteDeployOptions, SiteGenerateRequest, SiteOfferInput

        payload = SiteGenerateRequest(
            offer=SiteOfferInput(
                product_name="Ebook de Receitas Fitness",
                niche="emagrecimento",
                target_geo="LATAM ESP",
                language="pt",
                headline="Receitas práticas para organizar sua alimentação",
                subheadline="Um guia direto para quem quer comer melhor sem complicar a rotina.",
                benefits=["Receitas simples", "Organização semanal", "Acesso imediato"],
                pain_points=["Falta de tempo", "Dificuldade de manter rotina"],
                social_proof="Criativo validado em dry-run pelo Brain.",
                guarantee="Acesso digital imediato",
                price_anchor="Oferta de validação",
                checkout_url="https://checkout.example.com/ebook-receitas-fitness",
                cta_text="Acessar agora",
            ),
            template="direct_response",
            deploy=SiteDeployOptions(provider="github_vercel", dry_run=True, repository_name="ebook-receitas-fitness", branch="main"),
        )
        return self.safe_generate(payload, product_name="Ebook de Receitas Fitness", niche="emagrecimento")

    def safe_generate(self, payload: SiteGenerateRequest, product_name: str = "", niche: str = "") -> dict[str, Any]:
        now = datetime.now(UTC)
        offer = payload.offer
        site_id = f"{_slug(offer.product_name)}-{uuid4().hex[:8]}"
        output_dir = self.output_root / site_id
        output_dir.mkdir(parents=True, exist_ok=True)

        index_file = output_dir / "index.html"
        css_file = output_dir / "styles.css"
        deploy_payload_file = output_dir / "deploy_payload.json"
        manifest_file = output_dir / "site_builder_safe_manifest.json"

        index_file.write_text(self._html(payload), encoding="utf-8")
        css_file.write_text(self._css(), encoding="utf-8")

        deploy_payload = {
            "provider_requested": payload.deploy.provider,
            "dry_run_forced": True,
            "deploy_real_executed": False,
            "repository_name": payload.deploy.repository_name,
            "branch": payload.deploy.branch,
            "files": ["index.html", "styles.css"],
            "warnings": [
                "Deploy real bloqueado.",
                "Dry-run ativo: nenhum provedor externo foi chamado.",
                "GitHub/Vercel/Netlify não foram chamados.",
                "Payload preparado apenas para revisão futura.",
            ],
        }
        deploy_payload_file.write_text(json.dumps(deploy_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        result = {
            "status": "ok",
            "agent": "SiteBuilderBridge",
            "mode": "site_builder_safe",
            "product_name": offer.product_name,
            "template": payload.template,
            "generated_at": now.isoformat(),
            "output_dir": str(output_dir),
            "preview_path": str(index_file),
            "files": [str(index_file), str(css_file)],
            "deploy_provider": payload.deploy.provider,
            "deploy_status": "dry_run_payload_ready" if payload.deploy.provider != "local" else "local_ready",
            "deploy_real_executed": False,
            "github_executed": False,
            "vercel_executed": False,
            "netlify_executed": False,
            "deploy_payload_path": str(deploy_payload_file),
            "manifest_file": str(manifest_file),
            "warnings": deploy_payload["warnings"],
            "next_action": "brain_review_before_orchestration_pipeline",
        }
        manifest_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        memory_result = self._store_memory(payload, result, product_name, niche)
        decision_result = self._store_decision(payload, result, product_name, niche)
        brain_review = self._review_with_brain(payload, result, product_name, niche)

        return {
            "status": "ok",
            "agent": "SiteBuilderBridge",
            "mode": "site_builder_safe",
            "site_builder": result,
            "memory_result": memory_result,
            "decision_feed_result": decision_result,
            "brain_review": brain_review,
        }

    def _html(self, payload: SiteGenerateRequest) -> str:
        offer = payload.offer
        benefits = "\n".join(f"<li>{html.escape(item)}</li>" for item in offer.benefits)
        pains = "\n".join(f"<li>{html.escape(item)}</li>" for item in offer.pain_points)
        social = html.escape(offer.social_proof or "")
        guarantee = html.escape(offer.guarantee or "")
        return f"""<!doctype html>
<html lang="{html.escape(offer.language)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(offer.product_name)}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">{html.escape(offer.niche)} • {html.escape(offer.target_geo)}</p>
      <h1>{html.escape(offer.headline)}</h1>
      <p class="subheadline">{html.escape(offer.subheadline)}</p>
      <a class="cta" href="{html.escape(offer.checkout_url)}">{html.escape(offer.cta_text)}</a>
    </section>
    <section class="grid">
      <div>
        <h2>Benefícios</h2>
        <ul>{benefits}</ul>
      </div>
      <div>
        <h2>Dores resolvidas</h2>
        <ul>{pains}</ul>
      </div>
    </section>
    <section class="proof">
      <p>{social}</p>
      <p>{guarantee}</p>
      <p>{html.escape(offer.price_anchor or "")}</p>
    </section>
  </main>
</body>
</html>
"""

    def _css(self) -> str:
        return """body{margin:0;font-family:Arial,sans-serif;background:#0f172a;color:#f8fafc}.page{max-width:980px;margin:0 auto;padding:48px 20px}.hero{padding:48px;border-radius:28px;background:#111827;border:1px solid #334155}.eyebrow{color:#38bdf8;text-transform:uppercase;letter-spacing:.12em}h1{font-size:44px;line-height:1.05;margin:12px 0}.subheadline{font-size:20px;color:#cbd5e1}.cta{display:inline-block;margin-top:24px;background:#facc15;color:#111827;font-weight:700;padding:16px 24px;border-radius:16px;text-decoration:none}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:28px}.grid>div,.proof{background:#1e293b;border-radius:22px;padding:24px}.proof{margin-top:20px;color:#e2e8f0}@media(max-width:760px){.grid{grid-template-columns:1fr}h1{font-size:34px}}"""

    def _store_memory(self, payload: SiteGenerateRequest, result: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        return self.memory.remember({
            "product_name": product_name or payload.offer.product_name,
            "niche": niche or payload.offer.niche,
            "campaign_stage": "SITE_BUILDER_SAFE",
            "outcome": "SAFE_DRY_RUN",
            "lesson": "SiteBuilder Safe gerou index, CSS, deploy payload e manifesto sem deploy real.",
            "learning": "Antes de OrchestrationPipeline, confirmar site local e manter deploy real bloqueado.",
            "metrics": {
                "deploy_real_executed": False,
                "files_count": len(result.get("files", [])),
            },
            "source": "SiteBuilderBridge",
            "output_dir": result.get("output_dir"),
        })

    def _store_decision(self, payload: SiteGenerateRequest, result: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        record = {
            "product_name": product_name or payload.offer.product_name,
            "campaign_stage": "SITE_BUILDER_SAFE",
            "decision": "SIM",
            "confidence": 84,
            "next_action": "brain_review_before_orchestration_pipeline",
            "positive_points": [
                "SiteBuilder Safe gerou arquivos estáticos.",
                "Deploy real permaneceu bloqueado.",
                "Payload de deploy foi criado apenas para revisão.",
            ],
            "negative_points": result.get("warnings", []),
            "blocked_reasons": [],
            "meta_risk": {},
            "historical_recommendation": "Não ativar OrchestrationPipeline completo antes da revisão do Brain.",
            "panoramic_view": "SiteBuilder saiu de legacy/stub para camada safe controlada.",
            "recommended_solution": "Usar output local e dry-run até a fábrica completa ser homologada.",
            "memory_used": {"site_builder_safe": True, "deploy_real": False},
        }
        return self.decision_feed.record_brain_decision(record, context={
            "product_name": product_name or payload.offer.product_name,
            "niche": niche or payload.offer.niche,
            "campaign_stage": "SITE_BUILDER_SAFE",
        })

    def _review_with_brain(self, payload: SiteGenerateRequest, result: dict[str, Any], product_name: str, niche: str) -> dict[str, Any]:
        return self.brain.review_before_campaign({
            "product_name": product_name or payload.offer.product_name,
            "niche": niche or payload.offer.niche,
            "campaign_stage": "V4",
            "budget_brl": 25,
            "metrics": {"connect_rate": 80, "roas": 1.1, "purchase_rate": 2},
            "copy": f"{payload.offer.headline}\n{payload.offer.subheadline}\n{payload.offer.cta_text}",
            "offer": "SiteBuilder Safe — página local sem deploy real.",
            "site_builder_safe": result,
        })
