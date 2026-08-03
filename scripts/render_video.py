#!/usr/bin/env python3
"""Renderizador de video para anuncio — 100% gratuito, sem nenhuma API paga.

Pilha usada (tudo livre e sem chave):
  - edge-tts  : voz neural da Microsoft, gratuita, vozes pt-BR nativas
  - Pillow    : monta os quadros com o texto da cena
  - ffmpeg    : ja vem instalado no runner do GitHub Actions

Produz um MP4 vertical (9x16) ou quadrado (1x1) com:
  - uma cena por linha do roteiro
  - narracao sincronizada (a duracao da cena segue o audio real)
  - legenda queimada no video
  - efeito Ken Burns (zoom lento) para nao ficar estatico
  - fade entre cenas

Uso:
    python scripts/render_video.py \
        --product "Massageador Cervical" \
        --script-file script.txt \
        --voice pt-BR-AntonioNeural \
        --aspect 9x16 \
        --out out/video-final.mp4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Aparencia
# ---------------------------------------------------------------------------

SIZES = {"9x16": (1080, 1920), "1x1": (1080, 1080), "16x9": (1920, 1080)}

# Paleta escura de alto contraste — legivel no feed, funciona sem imagem externa
PALETTES = [
    ((15, 17, 21), (34, 197, 94)),    # preto / verde
    ((10, 14, 30), (56, 189, 248)),   # azul escuro / ciano
    ((26, 10, 10), (248, 113, 113)),  # vinho / coral
    ((18, 14, 30), (167, 139, 250)),  # roxo / lavanda
]

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def run(cmd: list[str]) -> None:
    """Executa e falha alto se der erro — nada de sucesso silencioso."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("COMANDO FALHOU:", " ".join(cmd), file=sys.stderr)
        print(proc.stderr[-3000:], file=sys.stderr)
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Voz
# ---------------------------------------------------------------------------

async def _tts(text: str, voice: str, dest: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate="+8%")
    await communicate.save(str(dest))


def narrate(text: str, voice: str, dest: Path) -> float:
    """Gera o audio da cena e devolve a duracao real em segundos."""
    asyncio.run(_tts(text, voice, dest))
    if not dest.exists() or dest.stat().st_size < 1000:
        raise SystemExit(f"FALHA: edge-tts nao gerou audio para: {text[:60]!r}")
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(dest)],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip())


# ---------------------------------------------------------------------------
# Quadros
# ---------------------------------------------------------------------------

def make_frame(text: str, product: str, index: int, total: int,
               size: tuple[int, int], dest: Path) -> None:
    w, h = size
    bg, accent = PALETTES[index % len(PALETTES)]

    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)

    # Gradiente vertical sutil, para nao ficar chapado
    for y in range(h):
        f = y / h
        d.line(
            [(0, y), (w, y)],
            fill=(
                int(bg[0] + (accent[0] - bg[0]) * f * 0.16),
                int(bg[1] + (accent[1] - bg[1]) * f * 0.16),
                int(bg[2] + (accent[2] - bg[2]) * f * 0.16),
            ),
        )

    # Barra de progresso das cenas
    bar_h = 10
    d.rectangle([0, 0, w, bar_h], fill=(255, 255, 255, 40))
    d.rectangle([0, 0, int(w * (index + 1) / total), bar_h], fill=accent)

    # Marca do produto no topo
    fp = _font(int(w * 0.040))
    d.text((int(w * 0.06), int(h * 0.07)), product.upper(), font=fp, fill=accent)

    # Texto da cena, centralizado.
    #
    # ATENCAO: o Ken Burns amplia ate 1.14x, o que recorta ~12% de cada
    # borda no fim da cena. Por isso o texto so pode ocupar a AREA SEGURA
    # (78% da largura, 55% da altura) — senao palavras somem no zoom.
    SAFE_W = w * 0.78
    SAFE_H = h * 0.55

    fs = int(w * 0.082)
    wrap = 22

    def layout(size_px: int, cols: int):
        f = _font(size_px)
        txt = textwrap.fill(text.strip(), width=cols)
        bb = d.multiline_textbbox((0, 0), txt, font=f, spacing=int(size_px * 0.35))
        return f, txt, bb[2] - bb[0], bb[3] - bb[1]

    font, wrapped, tw, th = layout(fs, wrap)

    # Encolhe ate caber na area segura em largura E altura.
    # MENOS colunas => linhas mais curtas (o inverso quebra o layout).
    guard = 0
    while (tw > SAFE_W or th > SAFE_H) and guard < 60:
        if tw > SAFE_W and wrap > 10:
            wrap -= 1
        else:
            fs = int(fs * 0.92)
            if fs < 26:
                break
        font, wrapped, tw, th = layout(fs, wrap)
        guard += 1

    x, y = (w - tw) / 2, (h - th) / 2

    # Sombra para garantir leitura
    d.multiline_text((x + 4, y + 4), wrapped, font=font, fill=(0, 0, 0),
                     align="center", spacing=int(fs * 0.35))
    d.multiline_text((x, y), wrapped, font=font, fill=(245, 245, 245),
                     align="center", spacing=int(fs * 0.35))

    # Faixa de destaque embaixo do bloco
    d.rectangle([x - 24, y + th + 28, x - 8, y + th + 34], fill=accent)

    img.save(dest, quality=95)


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------

def build_scene(frame: Path, audio: Path, dur: float, size: tuple[int, int],
                dest: Path) -> None:
    """Ken Burns (zoom lento) + audio da cena."""
    w, h = size
    fps = 30
    frames = max(int(dur * fps), 1)
    # zoompan precisa de imagem maior para ter para onde caminhar
    zoom = "zoompan=z='min(zoom+0.0009,1.14)':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}".format(
        n=frames, w=w, h=h, fps=fps
    )
    run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(frame),
        "-i", str(audio),
        "-vf", f"scale={w*2}:{h*2},{zoom},format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-t", f"{dur:.3f}",
        "-movflags", "+faststart",
        str(dest),
    ])


def concat(scenes: list[Path], dest: Path) -> None:
    lst = dest.parent / "lista.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in scenes), encoding="utf-8")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(dest),
    ])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--script-file", required=True)
    ap.add_argument("--voice", default="pt-BR-AntonioNeural")
    ap.add_argument("--aspect", default="9x16", choices=list(SIZES))
    ap.add_argument("--out", default="out/video-final.mp4")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        raise SystemExit("FALHA: ffmpeg nao encontrado no ambiente.")

    raw = Path(args.script_file).read_text(encoding="utf-8")
    scenes_text = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not scenes_text:
        raise SystemExit("FALHA: roteiro vazio.")

    size = SIZES[args.aspect]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="render_"))
    parts: list[Path] = []
    report = {"product": args.product, "aspect": args.aspect,
              "voice": args.voice, "scenes": []}

    total = len(scenes_text)
    for i, text in enumerate(scenes_text):
        print(f"[{i+1}/{total}] {text[:70]}")
        audio = work / f"a{i}.mp3"
        dur = narrate(text, args.voice, audio)
        dur = max(dur + 0.45, 1.8)  # respiro no fim da fala

        frame = work / f"f{i}.jpg"
        make_frame(text, args.product, i, total, size, frame)

        scene = work / f"s{i}.mp4"
        build_scene(frame, audio, dur, size, scene)
        parts.append(scene)
        report["scenes"].append({"index": i, "text": text, "seconds": round(dur, 2)})

    concat(parts, out)

    if not out.exists() or out.stat().st_size < 50_000:
        raise SystemExit("FALHA: video final vazio ou pequeno demais.")

    report["output"] = str(out)
    report["bytes"] = out.stat().st_size
    report["total_seconds"] = round(sum(s["seconds"] for s in report["scenes"]), 2)
    (out.parent / "render-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\nOK — video gerado")
    print(f"  arquivo : {out}")
    print(f"  tamanho : {report['bytes']/1_000_000:.2f} MB")
    print(f"  duracao : {report['total_seconds']}s em {total} cenas")

    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
