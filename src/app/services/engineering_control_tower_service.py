"""Missões 112-121 - Engineering Control Tower v2.0.

Serviço somente leitura que consolida saúde de engenharia, refatoração,
dependências, arquitetura, documentação, inteligência operacional,
simulação, estabilidade, operações e certificação de evolução em uma única
tela. Não chama rede externa; usa arquivos e serviços internos existentes.
"""

from __future__ import annotations

import ast
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.api.safe_router import FAILED_ROUTES, LOADED_ROUTES, ROUTE_COLLISIONS
from app.core.config import project_root
from app.services.architecture_audit_service import ArchitectureAuditService
from app.services.code_review_service import CodeReviewService
from app.services.dependency_audit_service import DependencyAuditService
from app.services.observability import component_health_snapshot
from app.services.operational_intelligence_service import OperationalIntelligenceService
from app.services.unified_certification_service import UnifiedCertificationEngine

UTC = timezone.utc


def _run_git(root: Path, *args: str) -> dict[str, Any]:
    """Executa consulta Git local em modo somente leitura."""
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


class EngineeringControlTowerService:
    """Agrega evidências das Missões 112-121 em snapshot executivo único."""

    def __init__(self, db: Any | None = None, root: Path | None = None):
        self.db = db
        self.root = root or project_root()
        self.app_root = self.root / "src" / "app"

    def _python_files(self) -> list[Path]:
        excluded = {"tests", "__pycache__", "migrations"}
        return [p for p in sorted(self.app_root.rglob("*.py")) if not any(part in excluded for part in p.parts)]

    def _engineering_modules(self) -> dict[str, Any]:
        services = sorted((self.app_root / "services").glob("*_service.py"))
        routes = sorted((self.app_root / "api" / "routes").glob("*.py"))
        schemas = sorted((self.app_root / "schemas").glob("*.py"))
        status = "healthy" if not FAILED_ROUTES and not ROUTE_COLLISIONS else "attention"
        return {
            "status": status,
            "services": len(services),
            "routes": len(routes),
            "schemas": len(schemas),
            "loaded_routes": len(LOADED_ROUTES),
            "failed_routes": FAILED_ROUTES,
            "route_collisions": ROUTE_COLLISIONS,
        }

    def _branch_inventory(self) -> dict[str, Any]:
        local = _run_git(self.root, "branch", "--format=%(refname:short)")
        remote = _run_git(self.root, "branch", "-r", "--format=%(refname:short)")
        current = _run_git(self.root, "branch", "--show-current")
        remotes = _run_git(self.root, "remote", "-v")
        remote_lines = _split_lines(remotes["stdout"])
        return {
            "status": "reviewed" if local["ok"] else "attention",
            "current_branch": current["stdout"] or None,
            "local_branches": _split_lines(local["stdout"]),
            "remote_branches": _split_lines(remote["stdout"]),
            "github_remote_configured": any("github.com" in line for line in remote_lines),
            "remotes": remote_lines,
            "notes": [] if remote_lines else ["Nenhum remote Git configurado neste ambiente local."],
        }

    def _pull_requests(self, branches: dict[str, Any] | None = None) -> dict[str, Any]:
        # Sem token/CLI GitHub obrigatório: registra prontidão local e evidências para homologação.
        branch_snapshot = branches or self._branch_inventory()
        reports = sorted(self.root.glob("*_REPORT.md"))
        pr_ready = bool(branch_snapshot["current_branch"]) and not ROUTE_COLLISIONS
        return {
            "status": "ready_for_homologation" if pr_ready else "attention",
            "provider": "local_git_and_make_pr",
            "current_branch": branch_snapshot["current_branch"],
            "github_remote_configured": branch_snapshot["github_remote_configured"],
            "reports_available": len(reports),
            "codeowners_present": (self.root / "CODEOWNERS").exists(),
            "merge_risk": "high" if ROUTE_COLLISIONS else "normal",
            "homologation_gate": "open_pr" if pr_ready else "review_required",
        }

    def _tests(self) -> dict[str, Any]:
        tests = sorted((self.app_root / "tests").glob("test_*.py"))
        root_tests = sorted(self.root.glob("test_*.py"))
        reports = sorted(self.root.glob("pytest*_output*.txt"))
        return {
            "status": "healthy" if tests else "attention",
            "test_files": len(tests) + len(root_tests),
            "pytest_reports": [p.name for p in reports[-5:]],
            "last_known_evidence": reports[-1].name if reports else None,
        }

    def _pipelines(self) -> dict[str, Any]:
        workflow_root = self.root / ".github" / "workflows"
        workflows = sorted(workflow_root.glob("*.yml")) + sorted(workflow_root.glob("*.yaml"))
        docker_files = [self.root / "Dockerfile", self.root / "docker-compose.yml"]
        validation_commands = [
            "pytest -q src/app/tests/test_m112_m121_engineering_control_tower.py",
            "pytest -q src/app/tests/test_route_security_guard.py src/app/tests/test_m112_m121_engineering_control_tower.py",
            "python -m compileall -q src/app/services/engineering_control_tower_service.py src/app/api/routes/engineering_control_tower.py",
        ]
        return {
            "status": "healthy" if workflows or any(p.exists() for p in docker_files) else "attention",
            "github_workflows": [str(path.relative_to(self.root)) for path in workflows],
            "github_workflow_count": len(workflows),
            "dockerfile": docker_files[0].exists(),
            "docker_compose": docker_files[1].exists(),
            "ci_validation": {
                "local_checks_defined": validation_commands,
                "remote_ci_status": "requires_github_push",
            },
        }

    def _teams(self) -> dict[str, Any]:
        codeowners = self.root / "CODEOWNERS"
        owners = []
        if codeowners.exists():
            owners = [line.strip() for line in codeowners.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
        return {"status": "mapped" if owners else "attention", "codeowners_rules": len(owners), "ownership_model": owners[:10]}

    def refactoring_report(self) -> dict[str, Any]:
        duplicates: dict[str, list[str]] = defaultdict(list)
        long_methods: list[dict[str, Any]] = []
        complex_classes: list[dict[str, Any]] = []
        imports_by_file: dict[str, set[str]] = {}
        for path in self._python_files():
            rel = str(path.relative_to(self.root))
            text = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            imports: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    key = f"{node.name}:{ast.dump(node, include_attributes=False)}"
                    duplicates[key].append(f"{rel}:{node.lineno}")
                    length = (node.end_lineno or node.lineno) - node.lineno + 1
                    branches = sum(isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.BoolOp, ast.Match)) for n in ast.walk(node))
                    if length > 55 or branches > 12:
                        long_methods.append({"file": rel, "name": node.name, "line": node.lineno, "lines": length, "complexity": branches})
                elif isinstance(node, ast.ClassDef):
                    methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    if len(methods) > 12:
                        complex_classes.append({"file": rel, "name": node.name, "line": node.lineno, "methods": len(methods)})
                elif isinstance(node, ast.Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
            imports_by_file[rel] = imports
        duplicated = [{"signature": k.split(":", 1)[0], "locations": v} for k, v in duplicates.items() if len(v) > 1]
        coupling = sorted(({"file": f, "imports": len(i)} for f, i in imports_by_file.items()), key=lambda x: x["imports"], reverse=True)[:10]
        suggestions = []
        if duplicated:
            suggestions.append({"priority": "high", "action": "Extrair funções duplicadas para serviço compartilhado.", "count": len(duplicated)})
        if long_methods:
            suggestions.append({"priority": "high", "action": "Quebrar métodos longos/complexos em unidades testáveis.", "count": len(long_methods)})
        if complex_classes:
            suggestions.append({"priority": "medium", "action": "Separar classes com muitas responsabilidades.", "count": len(complex_classes)})
        if coupling:
            suggestions.append({"priority": "medium", "action": "Revisar arquivos com maior acoplamento de imports.", "count": len(coupling)})
        return {"duplicated_code": duplicated[:20], "long_methods": long_methods[:20], "complex_classes": complex_classes[:20], "high_coupling": coupling, "prioritized_suggestions": suggestions}

    def _documentation(self) -> dict[str, Any]:
        docs = list(self.root.glob("*.md"))
        versioned = [p.name for p in docs if any(token in p.name.lower() for token in ("report", "release", "changelog", "roadmap"))]
        return {"status": "healthy" if (self.root / "README.md").exists() else "attention", "markdown_files": len(docs), "central_index": "README.md", "version_history_entries": len(versioned), "recent_records": versioned[-10:]}

    def _simulation_center(self) -> dict[str, Any]:
        scenarios = ["deploy", "rollback", "failures", "updates", "load_growth", "structural_changes"]
        evidence = ["run_r12_e2e.sh", "verificar_docker_O07.sh", "Dockerfile", "docker-compose.yml"]
        return {"status": "ready", "scenarios": scenarios, "evidence_files": [f for f in evidence if (self.root / f).exists()]}

    def _stability_program(self) -> dict[str, Any]:
        reports = [p.name for p in self.root.glob("*E2E*REPORT*.md")] + [p.name for p in self.root.glob("*LOAD*REPORT*.md")]
        return {"status": "monitored", "long_running_tests": bool(reports), "resource_trends": "available_via_observability", "evidence_reports": reports[:10]}

    def _legacy_certification(self, architecture: dict[str, Any], dependencies: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
        blockers = []
        if dependencies["missing_count"]:
            blockers.append("dependências ausentes")
        if review["total_blocking_findings"]:
            blockers.append("achados bloqueantes de revisão")
        if architecture.get("clean") is False:
            blockers.append("bloqueios arquiteturais")
        return {"status": "approved" if not blockers else "attention", "critical_blockers": blockers, "evidence_documented": True, "evolution_ready": not blockers}

    def snapshot(self) -> dict[str, Any]:
        dependencies = DependencyAuditService().audit()
        review = CodeReviewService().review_repository()
        architecture = ArchitectureAuditService().audit()
        certification = UnifiedCertificationEngine(self.db).certify() if self.db is not None else {"status": "not_connected"}
        operational = OperationalIntelligenceService(self.db).health_panel() if self.db is not None else {"status": "not_connected"}
        docs = self._documentation()
        stability = self._stability_program()
        legacy = self._legacy_certification(architecture, dependencies, review)
        branches = self._branch_inventory()
        global_sections = {
            "modules": self._engineering_modules(),
            "branches": branches,
            "pull_requests": self._pull_requests(branches),
            "tests": self._tests(),
            "pipelines": self._pipelines(),
            "certifications": certification,
            "teams": self._teams(),
        }
        section_statuses = [v.get("status", "unknown") for v in global_sections.values() if isinstance(v, dict)] + [legacy["status"], docs["status"]]
        return {
            "generated_at": datetime.now(UTC),
            "overall_status": "healthy" if all(s in {"healthy", "approved", "mapped", "monitored", "ready"} for s in section_statuses) else "attention",
            "global_status": global_sections,
            "refactoring": self.refactoring_report(),
            "dependency_health": dependencies,
            "architecture_consistency": architecture,
            "documentation_manager": docs,
            "operational_advisor": operational,
            "simulation_center": self._simulation_center(),
            "long_term_stability": stability,
            "enterprise_operations": component_health_snapshot(),
            "legacy_evolution_certification": legacy,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        snap = snapshot or self.snapshot()
        lines = ["# Engineering Control Tower - Fase v2.0", "", f"Gerado em: {snap['generated_at'].isoformat()}", f"Status global: **{snap['overall_status']}**", ""]
        lines.append("## Saúde global")
        for key, value in snap["global_status"].items():
            status = value.get("status", "unknown")
            lines.append(f"- {key}: {status}")
        branches = snap["global_status"].get("branches", {})
        pull_requests = snap["global_status"].get("pull_requests", {})
        pipelines = snap["global_status"].get("pipelines", {})
        lines.append(f"- branch atual: {branches.get('current_branch') or 'indisponível'}")
        lines.append(f"- PR homologação: {pull_requests.get('homologation_gate', 'unknown')}")
        lines.append(f"- CI remoto: {pipelines.get('ci_validation', {}).get('remote_ci_status', 'unknown')}")
        lines.append("")
        lines.append("## Recomendações priorizadas de refatoração")
        for item in snap["refactoring"]["prioritized_suggestions"]:
            lines.append(f"- {item['priority']}: {item['action']} ({item['count']})")
        if not snap["refactoring"]["prioritized_suggestions"]:
            lines.append("- Nenhuma recomendação crítica no momento.")
        lines.append("")
        lines.append(f"Dependências monitoradas: {snap['dependency_health']['total_declared']} | Issues: {len(snap['dependency_health']['issues'])}")
        lines.append(f"Certificação de evolução: {snap['legacy_evolution_certification']['status']}")
        return "\n".join(lines)
