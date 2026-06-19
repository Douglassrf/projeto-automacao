from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import wave
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from uuid import uuid4

import httpx

from app.core.config import get_settings, safe_project_path
from app.schemas.video_pipeline import VideoRenderRequest, VideoRenderResponse


def _safe_slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._ -]", "", value).strip().lower()
    value = re.sub(r"\s+", "-", value)
    return value[:80] or "produto"


def _escape_drawtext(value: str) -> str:
    # ffmpeg drawtext escaping: keep it simple and robust for generated marketing text.
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace("\n", " ")
    )[:520]


def _wrap(value: str, line_size: int = 26, max_lines: int = 4) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > line_size and current:
            lines.append(current)
            current = word
        else:
            current = candidate
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines or [value[:line_size]]


class VideoRenderPipeline:
    """Pipeline barato para vídeo: script -> voz -> cena -> montagem FFmpeg.

    Providers reais são opcionais. Sem chave externa, o pipeline usa fallback local
    determinístico para ainda entregar um .mp4 final testável dentro do War Kit.
    """

    def __init__(self):
        self.settings = get_settings()

    def render(self, payload: VideoRenderRequest) -> VideoRenderResponse:
        now = datetime.now(UTC)
        slug = _safe_slug(payload.product_name)
        render_id = f"{slug}-{payload.model.lower()}-{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        output_dir = safe_project_path(self.settings.kit_output_dir, "data/campaign_kits") / "Video_Renders" / render_id
        output_dir.mkdir(parents=True, exist_ok=True)

        script_file = output_dir / "script.md"
        audio_file = output_dir / "voiceover.wav"
        storyboard_file = output_dir / "storyboard.json"
        scene_file = output_dir / "scene_card.mp4"
        final_file = output_dir / f"{slug}_{payload.model}_final.mp4"

        duration = float(payload.duration_seconds or self._estimate_duration(payload.script))
        script_file.write_text(self._script_markdown(payload, duration), encoding="utf-8")
        warnings: list[str] = []

        provider_used = self._render_voice(payload, audio_file, duration, warnings)
        storyboard_file.write_text(json.dumps(self._storyboard(payload, duration), ensure_ascii=False, indent=2), encoding="utf-8")
        self._render_scene_with_ffmpeg(payload, scene_file, audio_file, final_file, duration, warnings)

        return VideoRenderResponse(
            product_name=payload.product_name,
            model=payload.model,
            generated_at=now,
            provider=provider_used,
            output_folder=str(output_dir),
            script_file=str(script_file),
            audio_file=str(audio_file),
            video_file=str(scene_file),
            final_mp4=str(final_file),
            duration_seconds=duration,
            status="created",
            warnings=warnings,
        )

    def _estimate_duration(self, script: str) -> int:
        words = len(script.split())
        return max(8, min(45, math.ceil(words / 2.5)))

    def _script_markdown(self, payload: VideoRenderRequest, duration: float) -> str:
        return f"""# Vídeo {payload.model} — {payload.product_name}

Duração estimada: {duration:.1f}s
Idioma: {payload.language}
Formato: {payload.aspect_ratio}

## Hook
{payload.hook}

## Roteiro
{payload.script}

## CTA
{payload.cta}
"""

    def _render_voice(self, payload: VideoRenderRequest, path: Path, duration: float, warnings: list[str]) -> str:
        requested = payload.voice_provider
        if requested in {"auto", "elevenlabs"} and self.settings.elevenlabs_api_key:
            try:
                self._render_elevenlabs(payload.script, path)
                return "elevenlabs"
            except Exception as exc:  # pragma: no cover - depends on external API
                warnings.append(f"ElevenLabs falhou; usando fallback local. Detalhe: {exc}")

        if requested in {"auto", "openai"} and self.settings.openai_api_key:
            try:
                self._render_openai_tts(payload.script, path)
                return "openai_tts"
            except Exception as exc:  # pragma: no cover - depends on external API
                warnings.append(f"OpenAI TTS falhou; usando fallback local. Detalhe: {exc}")

        self._write_silent_wav(path, duration)
        warnings.append("Voice-over externo não configurado; gerado áudio local silencioso para validar montagem.")
        return "fallback_local_silent_wav"

    def _render_elevenlabs(self, text: str, path: Path) -> None:  # pragma: no cover
        voice_id = self.settings.elevenlabs_voice_id or "EXAVITQu4vr4xnSDxMaL"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": self.settings.elevenlabs_api_key or "", "Content-Type": "application/json"}
        payload = {"text": text, "model_id": self.settings.elevenlabs_model, "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
        with httpx.Client(timeout=60) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            path.write_bytes(response.content)

    def _render_openai_tts(self, text: str, path: Path) -> None:  # pragma: no cover
        url = "https://api.openai.com/v1/audio/speech"
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}", "Content-Type": "application/json"}
        payload = {"model": self.settings.openai_tts_model, "voice": self.settings.openai_tts_voice, "input": text, "response_format": "wav"}
        with httpx.Client(timeout=60) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            path.write_bytes(response.content)

    def _write_silent_wav(self, path: Path, duration: float) -> None:
        sample_rate = 44100
        frames = int(duration * sample_rate)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"\x00\x00" * frames)

    def _storyboard(self, payload: VideoRenderRequest, duration: float) -> dict:
        return {
            "product_name": payload.product_name,
            "model": payload.model,
            "duration_seconds": duration,
            "scenes": [
                {"start": 0, "end": min(3, duration), "role": "hook", "text": payload.hook},
                {"start": min(3, duration), "end": max(duration - 4, 4), "role": "body", "text": payload.script[:500]},
                {"start": max(duration - 4, 0), "end": duration, "role": "cta", "text": payload.cta},
            ],
        }

    def _render_scene_with_ffmpeg(self, payload: VideoRenderRequest, scene_file: Path, audio_file: Path, final_file: Path, duration: float, warnings: list[str]) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg não está instalado no ambiente.")

        size = {"9:16": "720x1280", "1:1": "1080x1080", "16:9": "1280x720"}[payload.aspect_ratio]
        headline_lines = _wrap(payload.hook, 24, 3)
        cta_lines = _wrap(payload.cta, 28, 2)
        body = " ".join(payload.script.split())[:180]
        body_lines = _wrap(body, 31, 4)

        filters: list[str] = []
        y = 220
        for line in headline_lines:
            filters.append(f"drawtext=text='{_escape_drawtext(line)}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y={y}:box=1:boxcolor=black@0.35:boxborderw=18")
            y += 62
        y = 560
        for line in body_lines:
            filters.append(f"drawtext=text='{_escape_drawtext(line)}':fontcolor=white:fontsize=34:x=(w-text_w)/2:y={y}:box=1:boxcolor=black@0.25:boxborderw=14")
            y += 48
        y = 980 if payload.aspect_ratio == "9:16" else 610
        for line in cta_lines:
            filters.append(f"drawtext=text='{_escape_drawtext(line)}':fontcolor=yellow:fontsize=42:x=(w-text_w)/2:y={y}:box=1:boxcolor=black@0.45:boxborderw=18")
            y += 58
        vf = ",".join(filters)

        base_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x111827:s={size}:d={duration}",
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(scene_file),
        ]
        subprocess.run(base_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)

        final_cmd = [
            "ffmpeg", "-y",
            "-i", str(scene_file),
            "-i", str(audio_file),
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            str(final_file),
        ]
        subprocess.run(final_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
