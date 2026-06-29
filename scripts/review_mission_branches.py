#!/usr/bin/env python3
"""Review mission branches, PR readiness and CI state for homologation.

This helper is intentionally read-only by default. It inspects the configured Git
remote, finds branches whose name starts with ``missao-`` or ``mission-`` and
prints a Markdown homologation report. When ``--open-prs`` is provided it uses
GitHub CLI to create missing PRs, preserving the same validation summary.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

MISSION_PREFIXES = ("missao-", "mission-")


@dataclass(frozen=True)
class BranchReview:
    name: str
    head_sha: str
    has_pr: bool
    pr_url: str | None
    ci_state: str
    recommendation: str


def run(cmd: list[str], *, check: bool = True) -> str:
    completed = subprocess.run(cmd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return completed.stdout.strip()


def has_remote() -> bool:
    return bool(run(["git", "remote"], check=False).splitlines())


def remote_branches(remote: str) -> list[tuple[str, str]]:
    output = run(["git", "ls-remote", "--heads", remote], check=False)
    branches: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        sha, ref = line.split("\t", 1)
        name = ref.removeprefix("refs/heads/")
        if name.startswith(MISSION_PREFIXES):
            branches.append((name, sha))
    return sorted(branches)


def gh_available() -> bool:
    try:
        run(["gh", "--version"], check=True)
        return True
    except Exception:
        return False


def pr_for_branch(branch: str) -> tuple[bool, str | None]:
    if not gh_available():
        return False, None
    output = run(["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "url"], check=False)
    try:
        prs = json.loads(output or "[]")
    except json.JSONDecodeError:
        return False, None
    if not prs:
        return False, None
    return True, prs[0].get("url")


def ci_state_for_ref(ref: str) -> str:
    if not gh_available():
        return "unknown-gh-cli-unavailable"
    output = run(["gh", "run", "list", "--branch", ref, "--limit", "1", "--json", "status,conclusion"], check=False)
    try:
        runs = json.loads(output or "[]")
    except json.JSONDecodeError:
        return "unknown-gh-output"
    if not runs:
        return "no-ci-run-found"
    run_info = runs[0]
    status = run_info.get("status") or "unknown"
    conclusion = run_info.get("conclusion") or "pending"
    return f"{status}:{conclusion}"


def recommendation(has_pr: bool, ci_state: str) -> str:
    if ci_state.endswith(":success") and has_pr:
        return "ready-for-homologation"
    if not has_pr:
        return "open-pr-required"
    if "failure" in ci_state or "cancelled" in ci_state:
        return "fix-ci-before-homologation"
    return "wait-ci-validation"


def open_pr(branch: str, base: str) -> str | None:
    if not gh_available():
        return None
    title = f"Homologação: {branch}"
    body = "PR aberto automaticamente para homologação de branch de missão. Validar CI antes do merge."
    return run(["gh", "pr", "create", "--head", branch, "--base", base, "--title", title, "--body", body], check=False) or None


def review_branches(branches: Iterable[tuple[str, str]], *, open_prs: bool, base: str) -> list[BranchReview]:
    reviews: list[BranchReview] = []
    for branch, sha in branches:
        has_pr, pr_url = pr_for_branch(branch)
        if open_prs and not has_pr:
            pr_url = open_pr(branch, base)
            has_pr = bool(pr_url)
        ci_state = ci_state_for_ref(branch)
        reviews.append(BranchReview(branch, sha, has_pr, pr_url, ci_state, recommendation(has_pr, ci_state)))
    return reviews


def render_markdown(reviews: list[BranchReview], *, remote: str, base: str) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Relatório de homologação de branches de missão",
        "",
        f"- Gerado em: `{now}`",
        f"- Remote: `{remote}`",
        f"- Base alvo: `{base}`",
        f"- Branches analisadas: `{len(reviews)}`",
        "",
        "| Branch | SHA | PR | CI | Recomendação |",
        "| --- | --- | --- | --- | --- |",
    ]
    for review in reviews:
        pr = review.pr_url if review.pr_url else ("sim" if review.has_pr else "não")
        lines.append(f"| `{review.name}` | `{review.head_sha[:12]}` | {pr} | `{review.ci_state}` | `{review.recommendation}` |")
    if not reviews:
        lines.append("| _nenhuma branch missao-/mission- encontrada_ | - | - | - | - |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="origin", help="Remote Git a revisar")
    parser.add_argument("--base", default="main", help="Branch base para PRs de homologação")
    parser.add_argument("--open-prs", action="store_true", help="Cria PRs ausentes usando GitHub CLI")
    args = parser.parse_args()

    if not has_remote():
        print("ERRO: nenhum remote Git configurado; não é possível revisar branches no GitHub.", file=sys.stderr)
        return 2

    branches = remote_branches(args.remote)
    reviews = review_branches(branches, open_prs=args.open_prs, base=args.base)
    print(render_markdown(reviews, remote=args.remote, base=args.base))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
