from __future__ import annotations

import json
import re
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings, safe_project_path
from app.integrations.storage_provider import CampaignKitStorageProvider
from app.services.knowledge_engine import get_knowledge_engine
from app.schemas.war_kit import GeneratedFileItem, WarKitRequest, WarKitResponse
from app.schemas.video_pipeline import VideoRenderRequest
from app.services.video_pipeline import VideoRenderPipeline


def _safe_slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._ -]", "", value).strip().lower()
    value = re.sub(r"\s+", "-", value)
    return value[:80] or "produto"


class WarKitGenerator:
    """Agente de prompts + pipeline de saída.

    Por padrão usa templates locais determinísticos. Se OPENAI_API_KEY/Ollama estiverem
    configurados, este serviço pode ser estendido no método _agent_generate sem mexer
    nas rotas, dashboard ou estrutura de pastas.
    """

    def __init__(self, storage: CampaignKitStorageProvider | None = None):
        self.settings = get_settings()
        self.storage = storage or CampaignKitStorageProvider()
        self.knowledge = get_knowledge_engine()

    def generate(self, payload: WarKitRequest) -> WarKitResponse:
        now = datetime.now(UTC)
        slug = _safe_slug(payload.product.product_name)
        kit_id = f"{slug}-{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        root = safe_project_path(self.settings.kit_output_dir, "data/campaign_kits")
        kit = root / kit_id
        folders = {
            "root": kit,
            "creatives": kit / "Criativos",
            "copies": kit / "Copies",
            "pdfs": kit / "PDFs",
            "videos": kit / "Videos",
            "meta": kit / "Meta_Upload",
        }
        for folder in folders.values():
            folder.mkdir(parents=True, exist_ok=True)

        files: list[GeneratedFileItem] = []
        warnings: list[str] = []
        patterns = payload.mined_ads or []
        best = max(patterns, key=lambda x: (x.roas, x.connect_rate, x.active_ads), default=None)
        if not patterns:
            warnings.append("Nenhum anúncio minerado foi enviado; geração feita por templates locais baseados no DNA da oferta.")
        if payload.product.language == "auto_by_winning_ad":
            warnings.append("Idioma automático: revise o idioma final conforme o anúncio campeão antes de publicar.")

        strategy = self._strategy_json(payload, best)
        files.append(self._write_json(kit / "strategy_manifest.json", strategy, kit))
        files.append(self._write_text(kit / "README_KIT.md", self._readme(payload, strategy), kit, "readme"))
        files.append(self._write_json(kit / "knowledge_context.json", self.knowledge.marketing_context(), kit, "knowledge_context"))

        if payload.generate_copies:
            for model in ["V1", "V2", "V3"]:
                files.append(self._write_text(folders["copies"] / f"{model}_copy_pack.md", self._copy_pack(payload, model, best), kit, "copy"))

        if payload.generate_pdf:
            pdf_md = self._pdf_content(payload, best)
            files.append(self._write_text(folders["pdfs"] / f"{slug}_ebook_content.md", pdf_md, kit, "pdf_content"))
            files.append(self._write_minimal_pdf(folders["pdfs"] / f"{slug}_lead_magnet.pdf", payload.product.product_name, pdf_md, kit))

        if payload.generate_images:
            for model in ["V1", "V2", "V3"]:
                files.append(self._write_text(folders["creatives"] / f"{model}_image_prompts.md", self._image_prompts(payload, model, best), kit, "image_prompt"))

        if payload.generate_videos:
            for model in ["V1", "V2", "V3"]:
                video_script = self._video_scripts(payload, model, best)
                files.append(self._write_text(folders["videos"] / f"{model}_video_scripts.md", video_script, kit, "video_script"))
                if payload.render_video_assets:
                    render_request = VideoRenderRequest(
                        product_name=payload.product.product_name,
                        model=model,
                        hook=best.hook if best else f"Pare de perder tempo com {payload.product.main_pain}",
                        script=f"{payload.product.main_pain}. {payload.product.offer_promise}. {payload.product.desired_transformation}.",
                        cta=f"Acesse agora: {payload.product.affiliate_link or payload.product.checkout_url or payload.product.landing_page_url}",
                        language=payload.product.language,
                        voice_provider="auto",
                        scene_provider="ffmpeg_local",
                        duration_seconds=2,
                    )
                    if self.settings.war_kit_execute_video_render:
                        render_result = VideoRenderPipeline().render(render_request)
                        pointer = {
                            "mode": "rendered",
                            "model": model,
                            "final_mp4": render_result.final_mp4,
                            "audio_file": render_result.audio_file,
                            "script_file": render_result.script_file,
                            "provider": render_result.provider,
                            "warnings": render_result.warnings,
                        }
                    else:
                        pointer = {
                            "mode": "queued_render_job",
                            "model": model,
                            "provider": "ffmpeg_local_or_huggingface_svd",
                            "request": render_request.model_dump(mode="json"),
                            "note": "Render pesado separado do War Kit para manter o E2E rápido. Use POST /api/v1/video/render para gerar o MP4 final ou defina WAR_KIT_EXECUTE_VIDEO_RENDER=true."
                        }
                    files.append(self._write_json(folders["videos"] / f"{model}_render_result.json", pointer, kit, "video_render"))

        if payload.prepare_meta_upload:
            meta_payload = self._meta_upload_payload(payload, best)
            files.append(self._write_json(folders["meta"] / "meta_campaign_payload.json", meta_payload, kit, "meta_payload"))

        storage_result = self.storage.upload_folder(kit) if payload.push_to_storage else None
        folder_structure = {name: str(path.relative_to(kit)) if path != kit else "." for name, path in folders.items()}
        return WarKitResponse(
            product_name=payload.product.product_name,
            generated_at=now,
            provider=self.settings.ai_provider,
            output_root=str(root),
            kit_folder=str(kit),
            local_link=f"file://{kit}",
            total_files=len(files),
            files=files,
            folder_structure=folder_structure,
            meta_ready=payload.prepare_meta_upload,
            storage_status=storage_result.status if storage_result else "local_only_not_uploaded",
            warnings=warnings,
        )

    def _strategy_json(self, payload: WarKitRequest, best):
        context = self.knowledge.marketing_context()
        return {
            "product_dna": payload.product.model_dump(mode="json"),
            "winning_pattern_used": best.model_dump(mode="json") if best else None,
            "knowledge_core_files": sorted(self.knowledge.load_all().keys()),
            "campaign_models": {
                "V1": context["v1"],
                "V2": context["v2"],
                "V3": context["v3"],
            },
            "geo_rules": context["geo"],
            "pixel_rules": context["pixel"],
            "metrics_rules": context["metrics"],
            "copy_patterns": context["copy_patterns"],
            "creative_patterns": context["creative_patterns"],
            "guardrails": self.knowledge.guardrails(),
        }

    def _readme(self, payload, strategy):
        return f"""# Kit de Campanha — {payload.product.product_name}

## Estrutura
- Criativos: prompts de imagem por V1/V2/V3
- Copies: textos prontos para anúncio
- PDFs: conteúdo do lead magnet/material de suporte
- Videos: roteiros de vídeo
- Meta_Upload: payload pronto para o Meta AI Campaign Operator

## DNA da oferta
Nicho: {payload.product.niche}
Promessa: {payload.product.offer_promise}
Avatar: {payload.product.target_avatar}
Pixel: {payload.product.pixel_id}
GEO: {payload.product.geo_preset} | Países: {', '.join(payload.product.countries)}
"""

    def _copy_pack(self, payload, model, best):
        context = self.knowledge.marketing_context()
        strategy = context[model.lower()]
        copy_patterns = context["copy_patterns"].get("patterns", [])
        hook = best.hook if best else f"Você ainda sofre com {payload.product.main_pain}?"
        cta = best.cta_pattern if best else strategy.get("copy_style", {}).get("cta", "Comprar agora")
        tone = strategy.get("copy_style", {}).get("tone") or strategy.get("copy_style", {}).get("goal", "persuasiva e orientada a conversão")
        pattern_lines = "\n".join([f"- {item.get('name')}: {item.get('structure')}" for item in copy_patterns])
        return f"""# Copy Pack {model} — {payload.product.product_name}

## Knowledge Core usado
Estratégia: {strategy.get('name')}
Evento obrigatório: {strategy.get('conversion_event', 'Purchase')}
Tom: {tone}

## Padrões de copy disponíveis
{pattern_lines}

## Texto principal
{hook}

Se você quer {payload.product.desired_transformation}, este material foi criado para quem está no nicho de {payload.product.niche} e precisa de uma solução prática.

{payload.product.offer_promise}

👉 {cta}: {payload.product.affiliate_link or payload.product.checkout_url or payload.product.landing_page_url}

## Variações rápidas
1. Dor direta: {payload.product.main_pain} → solução: {payload.product.offer_promise}
2. Transformação: {payload.product.desired_transformation}
3. Prova/curiosidade: veja o método antes de decidir.

## Regras de campanha
{json.dumps(strategy.get('rules', {}), ensure_ascii=False, indent=2)}
"""

    def _pdf_content(self, payload, best):
        return f"""# {payload.product.product_name} — Material de Suporte

## Para quem é
{payload.product.target_avatar}

## Problema principal
{payload.product.main_pain}

## Transformação prometida
{payload.product.desired_transformation}

## Plano rápido
1. Entenda o problema.
2. Aplique a solução proposta.
3. Acesse a oferta completa.

## Chamada final
{payload.product.offer_promise}

Link: {payload.product.affiliate_link or payload.product.checkout_url or payload.product.landing_page_url}
"""

    def _image_prompts(self, payload, model, best):
        pattern = best.creative_pattern if best else "imagem limpa, benefício direto, alta legibilidade"
        return f"""# Prompts de Imagem {model}

1. Criar imagem para {payload.product.product_name} com padrão: {pattern}. Mostrar dor: {payload.product.main_pain}. Texto curto: {payload.product.offer_promise}.
2. Variação thumbnail: fundo contrastante, foco no benefício, CTA visual discreto.
3. Variação prova: visual de método/material digital, sem promessas proibidas.

Regra: manter formato original do criativo validado; não usar mídia flexível.
"""

    def _video_scripts(self, payload, model, best):
        hook = best.hook if best else f"Pare de perder tempo com {payload.product.main_pain}"
        return f"""# Roteiros de Vídeo {model}

## Roteiro 15–30s
0–3s Hook: {hook}
3–10s Dor: {payload.product.main_pain}
10–20s Solução: {payload.product.offer_promise}
20–30s CTA: acesse agora e veja o material completo.

## Direção
Formato UGC ou demonstração simples. Manter proporção original do criativo campeão.
"""

    def _meta_upload_payload(self, payload, best):
        return {
            "dry_run": True,
            "product_name": payload.product.product_name,
            "pixel_id": payload.product.pixel_id,
            "objective": "OUTCOME_SALES",
            "conversion_event": "Purchase",
            "final_link": str(payload.product.affiliate_link or payload.product.checkout_url or payload.product.landing_page_url),
            "geo": {"preset": payload.product.geo_preset, "countries": payload.product.countries, "excluded": payload.product.excluded_countries},
            "campaigns": ["V1", "V2", "V3"],
            "best_pattern": best.model_dump(mode="json") if best else None,
        }

    def _write_text(self, path: Path, content: str, kit_root: Path, kind: str="text") -> GeneratedFileItem:
        path.write_text(content, encoding="utf-8")
        return GeneratedFileItem(kind=kind, name=path.name, relative_path=str(path.relative_to(kit_root)), absolute_path=str(path))

    def _write_json(self, path: Path, data, kit_root: Path, kind: str="json") -> GeneratedFileItem:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return GeneratedFileItem(kind=kind, name=path.name, relative_path=str(path.relative_to(kit_root)), absolute_path=str(path))

    def _write_minimal_pdf(self, path: Path, title: str, markdown: str, kit_root: Path) -> GeneratedFileItem:
        text = (title + "\n\n" + re.sub(r"[#*_`>-]", "", markdown))[:1800]
        lines = [line[:90] for line in text.splitlines() if line.strip()][:35]
        stream = "BT /F1 12 Tf 50 780 Td "
        clean_lines = [line.encode('latin-1', 'ignore').decode('latin-1') for line in lines]
        for line in clean_lines:
            safe = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            stream += f"({safe}) Tj 0 -18 Td "
        stream += "ET"
        objects = [
            "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
            "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
            "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
            f"5 0 obj << /Length {len(stream.encode('latin-1', 'ignore'))} >> stream\n{stream}\nendstream endobj",
        ]
        pdf = "%PDF-1.4\n"
        offsets=[]
        for obj in objects:
            offsets.append(len(pdf.encode('latin-1')))
            pdf += obj + "\n"
        xref_pos=len(pdf.encode('latin-1'))
        pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n"
        for off in offsets:
            pdf += f"{off:010d} 00000 n \n"
        pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
        path.write_bytes(pdf.encode('latin-1', 'ignore'))
        return GeneratedFileItem(kind="pdf", name=path.name, relative_path=str(path.relative_to(kit_root)), absolute_path=str(path))
