"""Missao 126 - Intelligent Release Governance (Fase v2.1).

Quinta missao da Fase v2.1. Objetivo literal do briefing: "automatizar
a governanca das releases", com criterio "release somente liberada
quando todos os requisitos forem atendidos" - ou seja, um GATE
binario e fail-closed (mesmo principio das Missoes 50/53/60), nao um
observatorio continuo como a Missao 124 nem um planejador como a
Missao 125. As cinco validacoes exigidas pelo briefing, cada uma com
fonte real, nunca reimplementada (regra 7 do CLAUDE.md):

1. Testes -> reuso direto de
   `EnterpriseReadinessService.mission_test_coverage()` (Missao 60) -
   so este metodo leve, nunca o `readiness_report()` inteiro (mesma
   decisao ja documentada na Missao 124). Bloqueia a release quando
   alguma missao da timeline real do git nao tem suite dedicada em
   disco. Limitacao documentada com honestidade: isto mede COBERTURA
   de suite (existencia de arquivo `test_m<N>_*.py`), nao "os testes
   passaram agora" - nenhuma missao anterior deste projeto executa
   `pytest` como subprocesso a partir de um service (rodar a suite
   inteira de dentro de uma chamada HTTP/servico arriscaria o mesmo
   tipo de reentrancia perigosa documentada no commit da Missao 124
   sobre `ArchitectureStressTestService`, so que pior - um `pytest`
   filho rodando enquanto o processo pai pode estar dentro de uma
   sessao `pytest` de teste). Por isso esta missao nao inventa esse
   recurso novo - usa o sinal real mais forte que ja existe hoje.
2. Certificacoes -> reuso direto de
   `UnifiedCertificationEngine.certify()` (Missao 53), que por sua vez
   ja agrega a Certificacao Platinum (Missao 50) com os 11 criterios
   "Gold" recalculados ao vivo (nunca os `True` decorativos do Codex).
   Bloqueia quando `unified_certified` e `False`.
3. Seguranca -> reuso de `DependencyAuditService.audit()` (Missao 49).
   Decisao DELIBERADAMENTE diferente da Missao 124: la, `unpinned_count`
   nunca bloqueia (observatorio continuo, nao quer ficar vermelho para
   sempre por um padrao conhecido e aceito do projeto). Aqui, um GATE
   de release roda uma vez por release, nao continuamente - por isso e
   aceitavel exigir um padrao mais estrito: `unpinned_count == 0`
   bloqueia. Isto e uma politica explicita deste gate, documentada
   aqui, nao um bug: hoje (19/19 dependencias sem pin, ver
   `dependency_audit_service.py`) este criterio reprova de verdade, e
   essa reprovacao e o comportamento correto e esperado de um gate
   fail-closed, exatamente como `enterprise_ready: false` na Missao 60
   e `not_ready` no capstone das Missoes 71-80.
4. Documentacao -> reuso direto de `DocumentationService.live_snapshot()`
   (Missao 48): bloqueia quando ha algum modulo de rota que falhou ao
   carregar (`routes.failed > 0`, mesmo dado real que alimenta
   `safe_router.py` e o check "apis" da Missao 53) OU quando
   `validate_settings()` (Missao 41, via `settings_issues`) encontrou
   algum problema de configuracao - ou seja, a documentacao viva so e
   considerada "valida" quando o snapshot que ela gera reflete um
   sistema sem rota quebrada e sem problema de configuracao conhecido.
5. Dependencias -> reuso do MESMO `DependencyAuditService.audit()` do
   item 3 (chamada independente, mesmo padrao de cada eixo ser
   chamavel isoladamente que a Missao 124 ja usa), mas lendo os campos
   `missing_count` e `version_mismatch_count` - a leitura mais literal
   de "dependencias": elas estao presentes e na versao declarada?
   Bloqueia quando qualquer um dos dois e maior que zero. Note que
   Seguranca e Dependencias leem o MESMO relatorio real, mas campos
   DIFERENTES e com base diferente (continuo vs gate) - documentado
   aqui para nenhum leitor achar que e logica duplicada por acidente.

Veredito: `release_approved` so e `True` quando as cinco validacoes
acima passam ao mesmo tempo - fail-closed por design, igual a
`platinum_certified` (Missao 50), `unified_certified` (Missao 53) e
`enterprise_ready` (Missao 60). Nao existe um numero de qualidade
"quase aprovado" - ou os cinco requisitos estao atendidos, ou a
release fica bloqueada e a lista de `failed_requirements` mostra
exatamente quais."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.dependency_audit_service import DependencyAuditService
from app.services.documentation_service import DocumentationService
from app.services.enterprise_readiness_service import EnterpriseReadinessService
from app.services.unified_certification_service import UnifiedCertificationEngine

UTC = timezone.utc

_REQUIREMENT_NAMES = ("tests", "certifications", "security", "documentation", "dependencies")


class IntelligentReleaseGovernanceService:
    """Missao 126. Depende de `db` porque `EnterpriseReadinessService`
    (Missao 60) e `UnifiedCertificationEngine` (Missao 53) precisam de
    banco (cadeia ja documentada nessas missoes). `DocumentationService`
    (Missao 48) e `DependencyAuditService` (Missao 49) nao precisam -
    mesmo motivo ja documentado em `get_documentation_service()`-equivalente
    e `get_tech_debt_manager_service()` no container: leem so arquivo/config,
    nunca o banco."""

    def __init__(
        self,
        db: Session,
        enterprise_readiness: EnterpriseReadinessService | None = None,
        unified_certification: UnifiedCertificationEngine | None = None,
        documentation: DocumentationService | None = None,
        dependency_audit: DependencyAuditService | None = None,
    ) -> None:
        self.db = db
        self.enterprise_readiness = enterprise_readiness or EnterpriseReadinessService(db)
        self.unified_certification = unified_certification or UnifiedCertificationEngine(db)
        self.documentation = documentation or DocumentationService()
        self.dependency_audit = dependency_audit or DependencyAuditService()

    # --- cinco validacoes, cada uma chamavel isoladamente -------------------

    def tests_requirement(self) -> dict[str, Any]:
        """Testes: reuso direto de
        `EnterpriseReadinessService.mission_test_coverage()` (Missao 60).
        Ver limitacao honesta no docstring do modulo (cobertura de
        suite, nao execucao agora)."""
        coverage = self.enterprise_readiness.mission_test_coverage()
        return {
            "passed": coverage["complete"],
            "signal": "mission_test_coverage.complete",
            "detail": (
                f"{len(coverage['missions_without_dedicated_suite'])} missao(oes) "
                "sem suite dedicada em disco"
            ),
            "raw": coverage,
        }

    def certifications_requirement(self) -> dict[str, Any]:
        """Certificacoes: reuso direto de
        `UnifiedCertificationEngine.certify()` (Missao 53 - Platinum +
        Gold honesto)."""
        certification = self.unified_certification.certify()
        return {
            "passed": certification["unified_certified"],
            "signal": "unified_certified",
            "detail": (
                f"platinum_certified={certification['platinum_certified']}, "
                f"gold_certified={certification['gold_certified']}"
            ),
            "raw": certification,
        }

    def security_requirement(self) -> dict[str, Any]:
        """Seguranca: reuso de `DependencyAuditService.audit()` (Missao
        49), com a politica MAIS ESTRITA documentada no docstring do
        modulo (`unpinned_count` bloqueia aqui, diferente da Missao
        124)."""
        audit = self.dependency_audit.audit()
        passed = audit["unpinned_count"] == 0
        return {
            "passed": passed,
            "signal": "unpinned_count",
            "detail": f"{audit['unpinned_count']} dependencia(s) sem versao fixada em requirements.txt",
            "raw": audit,
        }

    def documentation_requirement(self) -> dict[str, Any]:
        """Documentacao: reuso direto de
        `DocumentationService.live_snapshot()` (Missao 48) - bloqueia
        com rota falha ou problema de configuracao real conhecido."""
        snapshot = self.documentation.live_snapshot()
        routes = snapshot["routes"]
        passed = routes["failed"] == 0 and len(snapshot["settings_issues"]) == 0
        return {
            "passed": passed,
            "signal": "routes.failed + settings_issues",
            "detail": (
                f"{routes['failed']} rota(s) falharam ao carregar, "
                f"{len(snapshot['settings_issues'])} problema(s) de configuracao"
            ),
            "raw": snapshot,
        }

    def dependencies_requirement(self) -> dict[str, Any]:
        """Dependencias: reuso do mesmo `DependencyAuditService.audit()`
        (Missao 49), lendo `missing_count`/`version_mismatch_count` -
        ver nota no docstring do modulo sobre a diferenca frente ao
        eixo de Seguranca."""
        audit = self.dependency_audit.audit()
        passed = audit["missing_count"] == 0 and audit["version_mismatch_count"] == 0
        return {
            "passed": passed,
            "signal": "missing_count + version_mismatch_count",
            "detail": (
                f"{audit['missing_count']} ausente(s), "
                f"{audit['version_mismatch_count']} com versao divergente"
            ),
            "raw": audit,
        }

    # --- agregacao (gate fail-closed) ---------------------------------------

    def validate_release(self) -> dict[str, Any]:
        requirements: dict[str, dict[str, Any]] = {
            "tests": self.tests_requirement(),
            "certifications": self.certifications_requirement(),
            "security": self.security_requirement(),
            "documentation": self.documentation_requirement(),
            "dependencies": self.dependencies_requirement(),
        }

        failed_requirements = sorted(name for name in _REQUIREMENT_NAMES if not requirements[name]["passed"])
        release_approved = len(failed_requirements) == 0

        return {
            "generated_at": datetime.now(UTC),
            "release_approved": release_approved,
            "failed_requirements": failed_requirements,
            "requirements": requirements,
        }

    def render_markdown(self, report: dict[str, Any] | None = None) -> str:
        report = report if report is not None else self.validate_release()
        requirements = report["requirements"]

        verdict = "RELEASE APROVADA" if report["release_approved"] else "RELEASE BLOQUEADA"
        lines: list[str] = [
            "# Governanca Inteligente de Release (Missao 126)",
            "",
            f"- Gerado em: {report['generated_at']}",
            f"- Veredito: **{verdict}**",
            "",
            "## Requisitos validados",
            "",
        ]
        for name in _REQUIREMENT_NAMES:
            data = requirements[name]
            marker = "OK" if data["passed"] else "BLOQUEANTE"
            lines.append(f"- `{name}`: {marker} - {data['signal']} ({data['detail']})")

        if report["failed_requirements"]:
            lines.append("")
            lines.append(
                f"## Requisitos que bloqueiam a release: {report['failed_requirements']}"
            )

        lines.append("")
        lines.append(
            "**IMPORTANTE**: este gate e fail-closed por design (mesmo principio das "
            "Missoes 50/53/60) - so aprova quando os cinco requisitos sao atendidos "
            "ao mesmo tempo. Uma reprovacao reflete o estado real do repositorio "
            "(ex.: dependencias sem pin, alertas abertos), nao um defeito desta "
            "missao."
        )

        return "\n".join(lines)
