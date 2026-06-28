"""Missao 53 - Unified Certification Engine.

Contexto real (nao hipotetico): duas certificacoes coexistiam no
repositorio sem se falar uma com a outra.

- `CertificationService` (Missao 50, "Platinum",
  app/services/certification_service.py) - calcula o veredito a partir de
  estado vivo do sistema (diagnosticos, alertas, auditoria de dependencias,
  recuperacao de fila). E "fail-closed": nunca aprova nada que nao tenha
  sido genuinamente verificado.
- `gold_certification_snapshot()` (Codex, Missoes 31-40, "Gold",
  app/core/production_readiness.py) - os 11 criterios sao literais `True`
  fixos no codigo-fonte (`{"audit": True, "docker": True, ...}`), sem
  calculo nenhum por tras. Sempre retorna "ready_for_review", independente
  do estado real do sistema (ver
  RELATORIO_MISSOES_CLAUDE_41_50_E_CODEX_31_40.md, secao 2, para a analise
  original que identificou isso).

Esta missao NAO apaga nem reescreve `gold_certification_snapshot()` - e
codigo de outro agente, ja mesclado em `master`; alterar o arquivo de
outra missao sem mandato especifico para isso esta fora de escopo.
`UnifiedCertificationEngine`, em vez disso, e a fonte de verdade nova: (1)
reusa o veredito Platinum sem reimplementa-lo; (2) recalcula os MESMOS 11
nomes de criterio que o Gold declara, mas com leitura real de estado do
sistema. 10 dos 11 passam a ser genuinamente verificados (arquivo no disco,
hash chain de auditoria, settings carregadas, diagnostico vivo, rotas
carregadas, auditoria de dependencias). O unico criterio que nao tem,
hoje, uma verificacao automatizada disponivel (`performance` - exigiria
rodar um teste de carga real contra um servidor em execucao, fora do
escopo de uma chamada de certificacao) e marcado explicitamente como
`verified: False` em vez de fingir `True`.

Criterio de sucesso: nenhum campo de `gold_checks` neste motor e um valor
fixo no codigo - cada `passed` e produto de uma leitura real, ou o campo
`verified` correspondente e `False`, declarando honestamente que aquele
criterio nao foi checado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings, project_root
from app.services.certification_service import CertificationService
from app.services.diagnostics_service import STATUS_OK, DiagnosticsService
from app.services.observability import immutable_audit_health, observability_health
from app.services.recovery_service import RecoveryService

UTC = timezone.utc

# Valor padrao de fabrica de app/core/config_domains/security.py - se o
# ambiente ainda usa este valor, a chave JWT nunca foi trocada.
_INSECURE_DEFAULT_JWT_SECRET = "change-me-super-secret-local-key"

# Mesmos 11 nomes de criterio declarados em
# production_readiness.gold_certification_snapshot() - preservados de
# proposito, para que o resultado seja comparavel 1:1 com o snapshot antigo.
GOLD_CHECK_NAMES: tuple[str, ...] = (
    "audit",
    "docker",
    "security",
    "performance",
    "governance",
    "recovery",
    "logs",
    "apis",
    "database",
    "documentation",
    "ci_cd",
)


class UnifiedCertificationEngine:
    """Missao 53. Une o veredito Platinum (Missao 50, real) com uma versao
    honesta dos 11 criterios "Gold" do Codex (Missoes 31-40) - ver docstring
    do modulo. Estritamente de leitura: nenhum metodo aqui escreve no banco
    (mesma garantia documentada em CertificationService)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.platinum_service = CertificationService(db)
        self.diagnostics = DiagnosticsService(db)
        self.recovery = RecoveryService(db)

    # -- cada check devolve (passed, detail) ---------------------------

    def _check_audit(self) -> tuple[bool, str]:
        health = immutable_audit_health()
        ok = bool(health["hash_chain_ok"]) and health["total_events"] > 0
        return ok, f"hash_chain_ok={health['hash_chain_ok']}, total_events={health['total_events']}"

    def _check_docker(self) -> tuple[bool, str]:
        dockerfile = project_root() / "Dockerfile"
        return dockerfile.exists(), f"Dockerfile em {dockerfile}"

    def _check_security(self) -> tuple[bool, str]:
        secret_changed = self.settings.jwt_secret_key != _INSECURE_DEFAULT_JWT_SECRET
        ok = bool(self.settings.auth_required) and secret_changed
        return ok, f"auth_required={self.settings.auth_required}, jwt_secret_key_alterado={secret_changed}"

    def _check_performance(self) -> tuple[bool, str]:
        # Deliberadamente sempre False/nao-verificado: nenhum teste de
        # carga real e executado por esta checagem (ver verified=False em
        # gold_style_checks() - isto NUNCA deve virar True sem um teste de
        # carga de fato ter rodado).
        return False, "nao verificado: nenhum teste de carga real foi executado por este check"

    def _check_governance(self) -> tuple[bool, str]:
        doc = project_root() / "docs" / "PRODUCTION_READINESS_MISSIONS_31_40.md"
        if not doc.exists():
            return False, f"{doc} nao encontrado"
        text = doc.read_text(encoding="utf-8").lower()
        ok = "missão oficialmente aprovada" in text or "missao oficialmente aprovada" in text
        return ok, f"regra de governanca presente em {doc.name}: {ok}"

    def _check_recovery(self) -> tuple[bool, str]:
        report = self.recovery.recovery_report()
        return bool(report["healthy"]), f"fila saudavel={report['healthy']}"

    def _check_logs(self) -> tuple[bool, str]:
        health = observability_health()
        ok = bool(health["enabled"]) and (health["log_file_exists"] or health["audit_file_exists"])
        return ok, f"observability_enabled={health['enabled']}, log_file_exists={health['log_file_exists']}"

    def _check_apis(self) -> tuple[bool, str]:
        from app.api.safe_router import FAILED_ROUTES, LOADED_ROUTES

        ok = len(FAILED_ROUTES) == 0
        return ok, f"{len(LOADED_ROUTES)} rota(s) carregada(s), {len(FAILED_ROUTES)} falharam"

    def _check_database(self, diagnostics_checks: list[dict[str, Any]]) -> tuple[bool, str]:
        db_check = next((c for c in diagnostics_checks if c["name"] == "database"), None)
        ok = bool(db_check and db_check["status"] == STATUS_OK)
        return ok, f"diagnostico de database: {db_check['status'] if db_check else 'ausente'}"

    def _check_documentation(self) -> tuple[bool, str]:
        ok = bool(self.settings.documentation_redact_secrets)
        return ok, f"documentation_redact_secrets={ok}"

    def _check_ci_cd(self) -> tuple[bool, str]:
        workflows_dir = project_root() / ".github" / "workflows"
        files = sorted(p.name for p in workflows_dir.glob("*.yml")) if workflows_dir.exists() else []
        return len(files) > 0, f"{len(files)} workflow(s): {', '.join(files) or 'nenhum'}"

    def gold_style_checks(self, diagnostics_checks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Recalcula, ao vivo, os mesmos 11 nomes de criterio que
        `gold_certification_snapshot()` (Codex) declara como `True` fixo.
        Cada entrada tem `passed` (resultado da checagem) e `verified`
        (a checagem foi de fato executada - quando False, `passed` e
        sempre False tambem, nunca um `True` nao verificado)."""

        checks_by_name: dict[str, Callable[[], tuple[bool, str]]] = {
            "audit": self._check_audit,
            "docker": self._check_docker,
            "security": self._check_security,
            "performance": self._check_performance,
            "governance": self._check_governance,
            "recovery": self._check_recovery,
            "logs": self._check_logs,
            "apis": self._check_apis,
            "database": lambda: self._check_database(diagnostics_checks),
            "documentation": self._check_documentation,
            "ci_cd": self._check_ci_cd,
        }
        unverified_names = {"performance"}

        result: dict[str, dict[str, Any]] = {}
        for name in GOLD_CHECK_NAMES:
            passed, detail = checks_by_name[name]()
            verified = name not in unverified_names
            result[name] = {"passed": bool(passed) and verified, "verified": verified, "detail": detail}
        return result

    def certify(self) -> dict[str, Any]:
        """Roda a certificacao unificada agora. Leitura pura."""

        platinum_snapshot = self.platinum_service.certify()
        diagnostics_result = self.diagnostics.run_full_diagnostics()
        gold_checks = self.gold_style_checks(diagnostics_result["checks"])

        verified_checks = {name: c for name, c in gold_checks.items() if c["verified"]}
        unverified_names = sorted(name for name, c in gold_checks.items() if not c["verified"])
        gold_certified = bool(verified_checks) and all(c["passed"] for c in verified_checks.values())

        unified_certified = bool(platinum_snapshot["platinum_certified"] and gold_certified)

        return {
            "generated_at": datetime.now(UTC),
            "platinum_certified": platinum_snapshot["platinum_certified"],
            "platinum": platinum_snapshot,
            "gold_certified": gold_certified,
            "gold_checks": gold_checks,
            "gold_unverified_check_names": unverified_names,
            "unified_certified": unified_certified,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.certify()

        lines: list[str] = []
        verdict = "CERTIFICADO" if report["unified_certified"] else "NAO CERTIFICADO"
        lines.append(f"# Certificacao Unificada (Missao 53) - {verdict}")
        lines.append("")
        lines.append(f"- Gerado em: {report['generated_at']}")
        lines.append(f"- Platinum (Missao 50): {'CERTIFICADO' if report['platinum_certified'] else 'NAO CERTIFICADO'}")
        lines.append(f"- Gold recalculado ao vivo: {'CERTIFICADO' if report['gold_certified'] else 'NAO CERTIFICADO'}")
        lines.append("")

        lines.append("## Criterios Gold (recalculados - nao mais hardcoded)")
        lines.append("")
        for name, check in report["gold_checks"].items():
            marker = "OK" if check["passed"] else ("NAO VERIFICADO" if not check["verified"] else "FALHOU")
            lines.append(f"- `{name}`: {marker} - {check['detail']}")
        lines.append("")

        if report["gold_unverified_check_names"]:
            lines.append("## Criterios sem verificacao automatizada disponivel")
            lines.append("")
            lines.append(
                "Os seguintes criterios nao podem, hoje, ser comprovados por este motor "
                "(exigiriam infraestrutura/execucao fora do escopo de uma chamada de "
                "certificacao) e por isso nunca contam como aprovados: "
                + ", ".join(report["gold_unverified_check_names"])
                + "."
            )
            lines.append("")

        return "\n".join(lines)
