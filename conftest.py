from __future__ import annotations

import os
from pathlib import Path


def pytest_configure(config):
    """Expose repository test shims before collection in locked-down runners."""
    tools_dir = Path(__file__).resolve().parent / "tools"
    os.environ["PATH"] = f"{tools_dir}{os.pathsep}{os.environ.get('PATH', '')}"
