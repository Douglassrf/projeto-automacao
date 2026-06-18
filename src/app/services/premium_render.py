from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFilter

from app.core.config import get_settings, safe_project_path
from app.schemas.premium_render import PremiumRenderRequest, PremiumRenderResponse, WorkerBlueprintResponse
from app.services.observability import log_event, observability_health, timed_event


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._ -]", "", value).strip().lower()
    value = re.sub(r"\s+", "-", value)
    return value[:80] or "asset"


def _mask_url(value: str | None) -> str:
    if not value:
        return "not-configured"
    if "@" in value:
        return value.split("@", 1)[0].split(":", 1)[0] + ":***@" + value.split("@", 1)[1]
    return value[:14] + "***"


def _safe_output_root(configured_dir: str) -> Path:
    return safe_project_path(configured_dir, "data/campaign_kits/PremiumRender")


class PremiumRenderPipeline:
    """Render premium em cadeia: geração -> upscale -> color grade.

    Providers pagos/externos ficam como dry-run/payload seguro por padrão. O fallback
    local cria um artefato real para testes e aplica pós-processamento com Pillow/FFmpeg.
    """

    def __init__(self):
        self.settings = get_settings()

    def render(self, payload: PremiumRenderRequest) -> PremiumRenderResponse:
        now = datetime.now(UTC)
        render_id = f"{_slug(payload.product_name)}-{payload.asset_type}-{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        output_dir = _safe_output_root(self.settings.premium_render_output_dir) / render_id
        output_dir.mkdir(parents=True, exist_ok=True)

        worker_payload_file = output_dir / "worker_payload.json"
        worker_payload_file.write_text(json.dumps(payload.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

        warnings: list[str] = []
        if payload.dispatch_mode == "celery" and not self.settings.celery_enabled:
            warnings.append("Celery está desativado; use dispatch_mode=local ou habilite CELERY_ENABLED=true.")
        if payload.dry_run or payload.provider == "dry_run":
            warnings.append("Dry-run ativo: nenhum provider premium externo foi chamado.")

        with timed_event("premium_render", {"provider": payload.provider, "asset_type": payload.asset_type, "dispatch_mode": payload.dispatch_mode}):
            if payload.asset_type == "image":
                base = self._create_or_copy_image(payload, output_dir, warnings)
                upscaled = self._upscale_image(base, output_dir) if payload.upscale else None
                source_for_grade = upscaled or base
                graded = self._color_grade_image(source_for_grade, output_dir, payload.color_grade) if payload.color_grade != "none" else None
                final = graded or source_for_grade
            else:
                base = self._create_or_copy_video(payload, output_dir, warnings)
                upscaled = self._upscale_video(base, output_dir, warnings) if payload.upscale else None
                source_for_grade = upscaled or base
                graded = self._color_grade_video(source_for_grade, output_dir, payload.color_grade, warnings) if payload.color_grade != "none" else None
                final = graded or source_for_grade

        event = log_event(
            "premium_render_completed",
            details={"render_id": render_id, "asset_type": payload.asset_type, "final_file": str(final), "warnings": warnings},
        )
        return PremiumRenderResponse(
            status="dry_run" if payload.dry_run or payload.provider == "dry_run" else "created",
            render_id=render_id,
            product_name=payload.product_name,
            asset_type=payload.asset_type,
            provider=payload.provider,
            dispatch_mode=payload.dispatch_mode,
            generated_at=now,
            output_folder=str(output_dir),
            base_asset_file=str(base),
            upscaled_file=str(upscaled) if upscaled else None,
            color_graded_file=str(graded) if 'graded' in locals() and graded else None,
            final_file=str(final),
            worker_payload_file=str(worker_payload_file),
            observability_event=event,
            warnings=warnings,
        )

    def _create_or_copy_image(self, payload: PremiumRenderRequest, output_dir: Path, warnings: list[str]) -> Path:
        target = output_dir / "01_generated_base.jpg"
        if payload.source_asset_path and Path(payload.source_asset_path).exists():
            shutil.copyfile(payload.source_asset_path, target)
            return target
        img = Image.new("RGB", (1080, 1080), "#111827")
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((70, 70, 1010, 1010), radius=40, fill="#1f2937", outline="#22d3ee", width=4)
        draw.text((110, 130), payload.product_name[:42], fill="#ffffff")
        draw.text((110, 230), payload.prompt[:220], fill="#d1d5db")
        draw.text((110, 880), "Premium Render Dry-Run", fill="#fde047")
        img.save(target, quality=92, optimize=True)
        warnings.append("Imagem base gerada localmente para teste; conecte Flux/SDXL para render premium real.")
        return target

    def _upscale_image(self, source: Path, output_dir: Path) -> Path:
        target = output_dir / "02_upscaled.jpg"
        with Image.open(source) as img:
            img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
            img = img.filter(ImageFilter.SHARPEN)
            img.save(target, quality=94, optimize=True)
        return target

    def _color_grade_image(self, source: Path, output_dir: Path, grade: str) -> Path:
        target = output_dir / f"03_color_{grade}.jpg"
        with Image.open(source) as img:
            img = img.convert("RGB")
            if grade in {"warm_contrast", "cinematic", "social_pop"}:
                # lightweight LUT-like adjustment without heavy OpenCV dependency.
                img = img.point(lambda p: min(255, int(p * 1.06 + 4)))
            img.save(target, quality=94, optimize=True)
        return target

    def _create_or_copy_video(self, payload: PremiumRenderRequest, output_dir: Path, warnings: list[str]) -> Path:
        target = output_dir / "01_generated_base.mp4"
        if payload.source_asset_path and Path(payload.source_asset_path).exists():
            shutil.copyfile(payload.source_asset_path, target)
            return target
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg é necessário para fallback de vídeo local.")
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x111827:s=720x1280:d=4",
            "-vf", f"drawtext=text='{payload.product_name[:36]}':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=360,drawtext=text='Premium Render Dry-Run':fontcolor=yellow:fontsize=34:x=(w-text_w)/2:y=880",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        warnings.append("Vídeo base gerado localmente para teste; conecte Runway/Kling/HF para render premium real.")
        return target

    def _upscale_video(self, source: Path, output_dir: Path, warnings: list[str]) -> Path | None:
        if shutil.which("ffmpeg") is None:
            warnings.append("FFmpeg ausente; upscale de vídeo ignorado.")
            return None
        target = output_dir / "02_upscaled.mp4"
        cmd = ["ffmpeg", "-y", "-i", str(source), "-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p", str(target)]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        return target

    def _color_grade_video(self, source: Path, output_dir: Path, grade: str, warnings: list[str]) -> Path | None:
        if shutil.which("ffmpeg") is None:
            warnings.append("FFmpeg ausente; color grade de vídeo ignorado.")
            return None
        target = output_dir / f"03_color_{grade}.mp4"
        vf = "eq=contrast=1.08:saturation=1.12:brightness=0.015" if grade != "none" else "null"
        cmd = ["ffmpeg", "-y", "-i", str(source), "-vf", vf, "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p", str(target)]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        return target


def worker_blueprint() -> WorkerBlueprintResponse:
    settings = get_settings()
    notes = [
        "Use Redis/Celery para volume alto de render premium; mantenha SQLite queue para uso pessoal/local.",
        "Tasks possuem retry automático no Celery e não travam a API principal.",
        "Monitore latência da fila, taxa de erro do render e tempo de resposta das APIs externas.",
    ]
    return WorkerBlueprintResponse(
        queue=settings.render_worker_queue,
        celery_enabled=settings.celery_enabled,
        broker_url_masked=_mask_url(settings.celery_broker_url),
        result_backend_masked=_mask_url(settings.celery_result_backend),
        start_command=f"cd server && celery -A app.workers.celery_app.celery_app worker -Q {settings.render_worker_queue} --loglevel=INFO",
        fallback_queue=settings.queue_backend,
        observability=observability_health(),
        notes=notes,
    )


class _ViralidadeRemodelTask:
    def delay(self, url, niche_identity):
        return {"status": "queued", "url": url, "niche_identity": niche_identity}


engine_viralidade_remodel = _ViralidadeRemodelTask()
