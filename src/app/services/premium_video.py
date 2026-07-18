"""Renderizador PREMIUM de video estilo TikTok viral (open source, sem GPU).

Formato dos anuncios campeoes de dropshipping: fotos/clipes reais do produto,
cortes rapidos (2-3s), movimento de camera (zoom Ken Burns), legendas grandes
no centro, narracao energetica + trilha. Este modulo monta exatamente isso com
FFmpeg + edge-tts a partir das imagens do produto.

Uso: passar 3-8 fotos do produto (URLs ou caminhos locais). Quanto melhores as
fotos (produto em uso, antes/depois, close), melhor o video.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from app.core.config import ensure_writable_dir, get_settings, safe_project_path
from app.services.video_pipeline import VideoRenderPipeline


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._ -]", "", value).strip().lower()
    return re.sub(r"\s+", "-", value)[:60] or "produto"


def _esc(value: str) -> str:
    return (
        value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%").replace("\n", " ")
    )[:200]


def _font() -> str:
    for c in (r"C:/Windows/Fonts/arialbd.ttf", r"C:/Windows/Fonts/impact.ttf", r"C:/Windows/Fonts/arial.ttf"):
        if Path(c).exists():
            return c.replace(":", "\\:")
    return ""


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("FFmpeg real nao encontrado no PATH.")
    return path


def _ffprobe_duration(path: Path) -> float:
    probe = shutil.which("ffprobe") or _ffmpeg().replace("ffmpeg", "ffprobe")
    out = subprocess.run(
        [probe, "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 30.0


def _phrases(script: str, count: int) -> list[str]:
    """Divide o roteiro em frases curtas de legenda (estilo TikTok)."""
    words = script.split()
    chunk = max(3, len(words) // max(count * 2, 1))
    phrases = [" ".join(words[i:i + chunk]) for i in range(0, len(words), chunk)]
    return [p for p in phrases if p][: count * 3]


class PremiumVideoRenderer:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _collect_images(self, sources: list[str], workdir: Path) -> list[Path]:
        images: list[Path] = []
        for i, src in enumerate(sources[:8]):
            target = workdir / f"img_{i}.jpg"
            try:
                if src.lower().startswith("http"):
                    with httpx.Client(timeout=30, follow_redirects=True) as client:
                        r = client.get(src)
                        r.raise_for_status()
                        target.write_bytes(r.content)
                else:
                    local = Path(src)
                    if local.exists():
                        shutil.copy(local, target)
                    else:
                        continue
                images.append(target)
            except Exception:
                continue
        return images

    def render(
        self,
        product_name: str,
        script: str,
        image_sources: list[str],
        cta: str = "COMPRAR AGORA",
        language: str = "pt-BR",
        music_path: str | None = None,
    ) -> dict:
        ffmpeg = _ffmpeg()
        now = datetime.now(timezone.utc)
        out_dir = safe_project_path(self.settings.kit_output_dir, "data/campaign_kits") / "Premium_Videos" / (
            f"{_slug(product_name)}-{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        )
        out_dir = ensure_writable_dir(out_dir)

        images = self._collect_images(image_sources, out_dir)
        if not images:
            return {"status": "error", "error": "no_images",
                    "message": "Nenhuma imagem valida. Envie 3-8 fotos do produto (URLs ou caminhos locais)."}

        # 1) Narracao (edge-tts gratuito via pipeline existente)
        voice_wav = out_dir / "voice.wav"
        vp = VideoRenderPipeline()
        warnings: list[str] = []
        try:
            vp._render_edge_tts(script, voice_wav, language)
            voice_provider = "edge_tts_free"
        except Exception as exc:
            vp._write_silent_wav(voice_wav, 30.0)
            voice_provider = "silent"
            warnings.append(f"edge-tts falhou: {exc}")

        total = min(max(_ffprobe_duration(voice_wav) + 1.0, 12.0), 60.0)
        n = len(images)
        scene_d = total / n

        # 2) Cada foto vira uma cena 1080x1920 com fundo desfocado + zoom Ken Burns
        font = _font()
        fps = 30
        inputs: list[str] = []
        chains: list[str] = []
        for i in range(n):
            inputs += ["-loop", "1", "-t", f"{scene_d:.3f}", "-i", str(images[i])]
            zoom_dir = "zoom+0.0018" if i % 2 == 0 else "if(eq(on,1),1.25,zoom-0.0018)"
            chains.append(
                f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                f"zoompan=z='{zoom_dir}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={int(scene_d * fps)}:s=1080x1920:fps={fps},setsar=1[v{i}]"
            )
        # Transicoes suaves (xfade) entre as cenas — visual de edicao profissional
        if n == 1:
            chains.append("[v0]null[base]")
        else:
            xf_d = 0.4
            prev = "v0"
            for i in range(1, n):
                out = f"x{i}" if i < n - 1 else "base"
                offset = scene_d * i - xf_d * i
                trans = ["fade", "slideleft", "circleopen", "fadeblack", "smoothup"][i % 5]
                chains.append(f"[{prev}][v{i}]xfade=transition={trans}:duration={xf_d}:offset={offset:.3f}[{out}]")
                prev = out

        # 3) Legendas grandes centrais, uma frase por vez (estilo viral)
        phrases = _phrases(script, n)
        seg = total / max(len(phrases), 1)
        subs = []
        for j, phrase in enumerate(phrases):
            start, end = j * seg, (j + 1) * seg
            words = phrase.split()
            mid = len(words) // 2 + len(words) % 2
            lines = [" ".join(words[:mid]), " ".join(words[mid:])] if len(words) > 4 else [phrase]
            y = 900
            for line in lines:
                if not line:
                    continue
                subs.append(
                    f"drawtext=fontfile='{font}':text='{_esc(line.upper())}':fontcolor=white:fontsize=64:"
                    f"borderw=6:bordercolor=black:x=(w-text_w)/2:y={y}:"
                    f"enable='between(t,{start:.2f},{end:.2f})'"
                )
                y += 84
        # CTA piscante no final
        subs.append(
            f"drawtext=fontfile='{font}':text='{_esc(cta.upper())}':fontcolor=yellow:fontsize=72:"
            f"borderw=6:bordercolor=black:x=(w-text_w)/2:y=1500:"
            f"enable='gte(t,{total - 4:.2f})*lt(mod(t\\,0.8)\\,0.55)'"
        )
        chains.append(f"[base]{','.join(subs)}[vid]")

        # 4) Audio: narracao + trilha opcional
        filter_complex = ";".join(chains)
        cmd = [ffmpeg, "-y", *inputs, "-i", str(voice_wav)]
        if music_path and Path(music_path).exists():
            cmd += ["-i", str(music_path)]
            filter_complex += f";[{n}:a]volume=1.0[voz];[{n + 1}:a]volume=0.12,aloop=loop=-1:size=2e9[trilha];[voz][trilha]amix=inputs=2:duration=first[aud]"
        else:
            filter_complex += f";[{n}:a]anull[aud]"
            if not music_path:
                warnings.append("Sem trilha sonora: no TikTok Ads, adicione um trending sound da biblioteca comercial ao subir.")

        final = out_dir / f"{_slug(product_name)}_viral.mp4"
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[vid]", "-map", "[aud]",
            "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(final),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=600)
        if proc.returncode != 0:
            return {
                "status": "error", "error": "ffmpeg_failed",
                "message": proc.stderr.decode(errors="ignore")[-800:],
            }

        return {
            "status": "ok",
            "final_video": str(final),
            "duration_seconds": round(total, 1),
            "scenes": n,
            "voice": voice_provider,
            "resolution": "1080x1920 (9:16)",
            "warnings": warnings,
            "output_folder": str(out_dir),
        }
