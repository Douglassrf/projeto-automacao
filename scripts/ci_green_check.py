"""Deterministic CI guard for Linux/Windows validation.

Runs syntax validation and pytest with an isolated SQLite database per attempt so
GitHub Actions never depends on local files left by previous jobs or test order.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], env: dict[str, str], timeout_seconds: int) -> None:
    print(f"::group::{ ' '.join(cmd) }")
    try:
        subprocess.run(cmd, cwd=ROOT, env=env, check=True, timeout=timeout_seconds)
    finally:
        print("::endgroup::")


def _attempt_env(attempt: int, base_tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    db_path = base_tmp / f"ci-attempt-{attempt}" / "adintelligence.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONFAULTHANDLER": "1",
            # Sem isto, stdout/stderr do subprocesso (compileall/pytest) fica
            # bufferizado em blocos quando nao esta preso a um console real -
            # e o caso do Windows runner do GitHub Actions. Se o subprocesso
            # travar/estourar o timeout, tudo que estava no buffer e perdido
            # (o processo morre antes de flush), e o log mostra zero linhas
            # de progresso mesmo que os testes estivessem rodando de verdade.
            "PYTHONUNBUFFERED": "1",
            "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
            "DEFAULT_ADMIN_PASSWORD": env.get("DEFAULT_ADMIN_PASSWORD", "test-only-admin-password"),
            "AUTH_REQUIRED": env.get("AUTH_REQUIRED", "true"),
            "META_DRY_RUN": "true",
            "META_AUTOPUBLISH": "false",
            "META_ALLOW_ACTIVE_LAUNCH": "false",
            "META_ALLOW_PRODUCTION_REAL": "false",
        }
    )
    if platform.system() == "Windows":
        env.setdefault("CI_SKIP_FFMPEG", "true")
    return env


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=int(os.environ.get("CI_GREEN_REPEAT", "1")))
    parser.add_argument("--pytest-args", default=os.environ.get("CI_PYTEST_ARGS", "-q"))
    parser.add_argument("--command-timeout", type=int, default=int(os.environ.get("CI_COMMAND_TIMEOUT", "1800")))
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")

    base_tmp = Path(tempfile.mkdtemp(prefix="projeto-automacao-ci-"))
    try:
        for attempt in range(1, args.repeat + 1):
            print(f"\n=== CI green attempt {attempt}/{args.repeat} on {platform.system()} ===")
            env = _attempt_env(attempt, base_tmp)
            _run([sys.executable, "-m", "compileall", "-q", "src"], env, args.command_timeout)
            pytest_cmd = [sys.executable, "-m", "pytest", *args.pytest_args.split()]
            if platform.system() == "Windows" and "-m" not in pytest_cmd:
                pytest_cmd.extend(["-m", "not ffmpeg"])
            _run(pytest_cmd, env, args.command_timeout)
        print(f"\nCI green certification: {args.repeat}/{args.repeat} clean attempts passed.")
        return 0
    finally:
        shutil.rmtree(base_tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
