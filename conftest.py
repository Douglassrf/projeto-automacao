from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_configure(config):
    """Expose repository test shims before collection in locked-down runners."""
    tools_dir = Path(__file__).resolve().parent / "tools"
    os.environ["PATH"] = f"{tools_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def pytest_collection_modifyitems(config, items):
    """Skip ffmpeg integration tests when shim/binary cannot execute."""
    import shutil
    import subprocess

    exe = shutil.which("ffmpeg")
    ffmpeg_ok = False
    if exe:
        try:
            ffmpeg_ok = subprocess.run(
                [exe, "-version"], capture_output=True, timeout=10
            ).returncode == 0
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            ffmpeg_ok = False
    if ffmpeg_ok:
        return
    skip = pytest.mark.skip(reason="ffmpeg indisponivel ou nao executavel (M82/M83)")
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if "test_ugc_processing.py" in nodeid and "blocks_dangerous" not in item.name:
            item.add_marker(skip)
        if "test_video_pipeline.py" in nodeid:
            item.add_marker(skip)
        if "ffmpeg" in item.keywords:
            item.add_marker(skip)
