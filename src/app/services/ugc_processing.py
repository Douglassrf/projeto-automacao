from __future__ import annotations

import json
import mimetypes
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.services.upload_security import BLOCKED_EXTENSIONS, secure_user_filename


class UGCProcessingError(ValueError):
    """Raised when a UGC asset cannot be safely processed."""


@dataclass(frozen=True)
class UGCProcessResult:
    status: str
    asset_id: str
    media_type: str
    original_filename: str
    safe_original_filename: str
    generated_at: datetime
    raw_path: str
    processed_path: str
    input_size_bytes: int
    output_size_bytes: int
    savings_percent: float
    target_preset: str
    ffmpeg_command: list[str]
    metadata: dict
    warnings: list[str]


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


class UGCEdgeProcessor:
    """Compresses and standardizes user generated creative assets before storage.

    This keeps storage and bandwidth low by transcoding images/videos on entry with FFmpeg.
    """

    def __init__(
        self,
        output_dir: str,
        max_size_bytes: int,
        image_target_width: int = 1080,
        video_target_width: int = 720,
        video_crf: int = 28,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
    ):
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.max_size_bytes = max_size_bytes
        self.image_target_width = image_target_width
        self.video_target_width = video_target_width
        self.video_crf = video_crf
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    def process(self, filename: str, content: bytes, target_preset: str = "social_ad") -> UGCProcessResult:
        if not content:
            raise UGCProcessingError("Arquivo vazio não pode ser processado.")

        if len(content) > self.max_size_bytes:
            raise UGCProcessingError(f"Arquivo acima do limite de UGC: {self.max_size_bytes} bytes.")

        safe_name = secure_user_filename(filename or "ugc_upload")
        ext = Path(safe_name).suffix.lower()

        if ext in BLOCKED_EXTENSIONS:
            raise UGCProcessingError("Extensão perigosa bloqueada para UGC.")

        if ext not in ALLOWED_EXTENSIONS:
            raise UGCProcessingError("UGC aceita apenas imagens (.jpg/.png/.webp) ou vídeos (.mp4/.mov/.webm/.mkv).")

        media_type = "image" if ext in IMAGE_EXTENSIONS else "video"
        guessed_mime, _ = mimetypes.guess_type(safe_name)
        if media_type == "image" and not (guessed_mime or "").startswith("image/"):
            raise UGCProcessingError("Extensão de imagem não compatível com MIME esperado.")
        if media_type == "video" and not (guessed_mime or "").startswith("video/"):
            # .mkv is often application/octet-stream in some environments; allow known video extension.
            if ext != ".mkv":
                raise UGCProcessingError("Extensão de vídeo não compatível com MIME esperado.")

        if not shutil.which(self.ffmpeg_bin):
            raise UGCProcessingError("FFmpeg não encontrado. Instale o ffmpeg para processar UGC.")

        asset_id = uuid4().hex
        asset_dir = self.output_dir / asset_id
        raw_dir = asset_dir / "raw"
        processed_dir = asset_dir / "processed"
        raw_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)

        raw_path = (raw_dir / safe_name).resolve()
        raw_path.write_bytes(content)

        metadata = self._probe(raw_path)
        warnings: list[str] = []

        if media_type == "image":
            processed_path = processed_dir / f"{asset_id}_optimized.jpg"
            command = self._image_command(raw_path, processed_path)
        else:
            processed_path = processed_dir / f"{asset_id}_optimized.mp4"
            command = self._video_command(raw_path, processed_path)

        self._run(command)

        if not processed_path.exists() or processed_path.stat().st_size <= 0:
            raise UGCProcessingError("FFmpeg não gerou arquivo processado válido.")

        input_size = len(content)
        output_size = processed_path.stat().st_size
        savings = round(max(0, 1 - (output_size / input_size)) * 100, 2) if input_size else 0.0

        if output_size > input_size:
            warnings.append("Arquivo processado ficou maior que o original; manter o original pode ser mais econômico nesse caso.")

        manifest = {
            "asset_id": asset_id,
            "media_type": media_type,
            "original_filename": filename,
            "safe_original_filename": safe_name,
            "raw_path": str(raw_path),
            "processed_path": str(processed_path.resolve()),
            "input_size_bytes": input_size,
            "output_size_bytes": output_size,
            "savings_percent": savings,
            "target_preset": target_preset,
            "metadata": metadata,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        (asset_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return UGCProcessResult(
            status="processed",
            asset_id=asset_id,
            media_type=media_type,
            original_filename=filename,
            safe_original_filename=safe_name,
            generated_at=datetime.now(timezone.utc),
            raw_path=str(raw_path),
            processed_path=str(processed_path.resolve()),
            input_size_bytes=input_size,
            output_size_bytes=output_size,
            savings_percent=savings,
            target_preset=target_preset,
            ffmpeg_command=command,
            metadata=metadata,
            warnings=warnings,
        )

    def _image_command(self, input_path: Path, output_path: Path) -> list[str]:
        return [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"scale='min({self.image_target_width},iw)':-2",
            "-q:v",
            "5",
            str(output_path),
        ]

    def _video_command(self, input_path: Path, output_path: Path) -> list[str]:
        return [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"scale='min({self.video_target_width},iw)':-2,fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(self.video_crf),
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def _run(self, command: list[str]) -> None:
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, check=False)
        if process.returncode != 0:
            raise UGCProcessingError(process.stderr.strip() or "Falha ao executar FFmpeg.")

    def _probe(self, input_path: Path) -> dict:
        if not shutil.which(self.ffprobe_bin):
            return {"ffprobe_available": False}
        process = subprocess.run(
            [
                self.ffprobe_bin,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if process.returncode != 0:
            return {"ffprobe_available": True, "probe_error": process.stderr.strip()}
        try:
            data = json.loads(process.stdout or "{}")
        except json.JSONDecodeError:
            data = {}
        streams = data.get("streams", [])
        return {
            "ffprobe_available": True,
            "format_name": data.get("format", {}).get("format_name"),
            "duration": data.get("format", {}).get("duration"),
            "bit_rate": data.get("format", {}).get("bit_rate"),
            "streams": [
                {
                    "codec_type": stream.get("codec_type"),
                    "codec_name": stream.get("codec_name"),
                    "width": stream.get("width"),
                    "height": stream.get("height"),
                }
                for stream in streams[:4]
            ],
        }
