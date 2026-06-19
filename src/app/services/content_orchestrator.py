from __future__ import annotations

import re
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from difflib import SequenceMatcher

from app.schemas.content_orchestrator import ContentOrchestratorRequest, ContentOrchestratorResponse


_IMAGE_TERMS = {"imagem", "foto", "banner", "thumbnail", "arte", "mockup", "capa", "criativo estático", "creative image"}
_VIDEO_TERMS = {"video", "vídeo", "reels", "ugc", "storyboard", "cena", "avatar", "voice over", "narração"}


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9áàâãéèêíóôõúçñü\s]", " ", text)
    return re.sub(r"\s+", " ", text)


class ContentOrchestrator:
    """Orquestrador determinístico para roteamento de conteúdo multimídia.

    Ele implementa as regras de agência: deduplicação, nota de qualidade e decisão de
    ferramenta. Em produção, o método de qualidade pode ser substituído por Gemini/RAG,
    mantendo o mesmo contrato JSON.
    """

    def route(self, payload: ContentOrchestratorRequest) -> ContentOrchestratorResponse:
        duplicate = self._find_duplicate(payload)
        quality = self._score_quality(payload)
        improvements = self._improvements(payload, quality)

        log = {
            "duplicado": duplicate is not None,
            "duplicado_com": duplicate,
            "qualidade_nota": quality,
            "threshold": payload.quality_threshold,
            "melhorias": improvements,
            "decisao_recurso": None,
        }

        if duplicate:
            return ContentOrchestratorResponse(
                status="erro",
                acao="Execução interrompida por duplicidade.",
                proximo_passo="revisar_ideia_ou_alterar_angulo",
                log=log,
                generated_payload=None,
                created_at=datetime.now(UTC),
            )

        if quality < payload.quality_threshold:
            return ContentOrchestratorResponse(
                status="erro",
                acao="Ideia abaixo do benchmark mínimo; melhorias sugeridas antes de executar.",
                proximo_passo="melhorar_brief_e_reenviar",
                log=log,
                generated_payload={"melhorias_recomendadas": improvements},
                created_at=datetime.now(UTC),
            )

        content_type = self._decide_type(payload)
        log["decisao_recurso"] = content_type
        generated_payload = self._build_tool_payload(payload, content_type)
        tool = generated_payload["tool"]
        action = {
            "text": "Conteúdo textual/lógico aprovado para execução interna.",
            "image": "Prompt de imagem criado e pronto para envio ao Hugging Face Stable Diffusion.",
            "video": "Prompt/roteiro de vídeo criado e pronto para envio ao Hugging Face ZeroGPU ou pipeline FFmpeg.",
        }[content_type]

        return ContentOrchestratorResponse(
            status="ok",
            acao=action,
            proximo_passo=tool,
            log=log,
            generated_payload=generated_payload,
            created_at=datetime.now(UTC),
        )

    def _find_duplicate(self, payload: ContentOrchestratorRequest) -> dict | None:
        new_title = _normalize(payload.title)
        new_brief = _normalize(payload.brief)
        for item in payload.existing_content:
            old_title = _normalize(item.title)
            title_score = SequenceMatcher(None, new_title, old_title).ratio()
            summary_score = 0.0
            if item.summary:
                summary_score = SequenceMatcher(None, new_brief[:500], _normalize(item.summary)[:500]).ratio()
            if title_score >= 0.86 or (title_score >= 0.72 and summary_score >= 0.60):
                return {"title": item.title, "title_similarity": round(title_score, 3), "summary_similarity": round(summary_score, 3)}
        return None

    def _score_quality(self, payload: ContentOrchestratorRequest) -> float:
        text = f"{payload.title} {payload.brief}".lower()
        score = 5.2
        if len(payload.brief) >= 180:
            score += 1.0
        if any(x in text for x in ["dor", "problema", "medo", "desejo", "transformação", "benefício"]):
            score += 0.9
        if any(x in text for x in ["cta", "comprar", "acessar", "clique", "agora"]):
            score += 0.8
        if any(x in text for x in ["público", "avatar", "persona", "cliente", "nicho"]):
            score += 0.7
        if any(x in text for x in ["prova", "métrica", "roas", "connect rate", "checkout", "purchase"]):
            score += 0.7
        if any(x in text for x in ["imagem", "vídeo", "pdf", "site", "anúncio", "criativo"]):
            score += 0.5
        return round(min(score, 10.0), 1)

    def _improvements(self, payload: ContentOrchestratorRequest, quality: float) -> list[str]:
        text = f"{payload.title} {payload.brief}".lower()
        tips: list[str] = []
        if len(payload.brief) < 180:
            tips.append("Detalhar melhor a promessa, o público e o contexto do criativo.")
        if not any(x in text for x in ["dor", "problema", "medo", "desejo", "transformação", "benefício"]):
            tips.append("Adicionar a dor principal e a transformação prometida.")
        if not any(x in text for x in ["cta", "comprar", "acessar", "clique", "agora"]):
            tips.append("Adicionar uma chamada de ação direta.")
        if not any(x in text for x in ["público", "avatar", "persona", "cliente", "nicho"]):
            tips.append("Informar o avatar ou nicho do público-alvo.")
        if quality >= payload.quality_threshold and not tips:
            tips.append("Brief aprovado; seguir execução.")
        return tips

    def _decide_type(self, payload: ContentOrchestratorRequest) -> str:
        if payload.desired_format != "auto":
            return payload.desired_format
        text = _normalize(f"{payload.title} {payload.brief}")
        if any(term in text for term in _VIDEO_TERMS):
            return "video"
        if any(term in text for term in _IMAGE_TERMS):
            return "image"
        return "text"

    def _build_tool_payload(self, payload: ContentOrchestratorRequest, content_type: str) -> dict:
        base_prompt = (
            f"Tema: {payload.title}. Brief: {payload.brief}. Plataforma: {payload.target_platform}. "
            "Criar conteúdo de alta conversão, direto, com promessa clara, emoção e CTA."
        )
        if content_type == "text":
            return {
                "tool": "internal_text_logic",
                "type": "text",
                "copy": {
                    "headline": payload.title,
                    "primary_text": payload.brief,
                    "cta": "Acesse agora",
                },
            }
        if content_type == "image":
            return {
                "tool": "huggingface_stable_diffusion",
                "type": "image",
                "prompt_midia": base_prompt + " Ultra realistic social media ad, cinematic lighting, high CTR, 4K, clean composition.",
            }
        return {
            "tool": "huggingface_zerogpu_video_or_ffmpeg_pipeline",
            "type": "video",
            "prompt_midia": base_prompt + " Short vertical ad video, strong 3-second hook, dynamic transitions, emotional CTA.",
            "scenes": [
                {"start": "0s", "role": "hook", "instruction": "Abrir com dor ou promessa forte."},
                {"start": "3s", "role": "body", "instruction": "Mostrar solução e prova simples."},
                {"start": "12s", "role": "cta", "instruction": "Chamada direta para ação."},
            ],
        }
