from __future__ import annotations

from app.core.sandbox_execution_contract import APPROVAL_PHRASE
from app.core.sandbox_readiness import sandbox_readiness_report
from app.core.security_status import security_hardening_status


def operational_handoff_checklist() -> dict:
    security = security_hardening_status()
    sandbox = sandbox_readiness_report({"target": "meta"})
    return {
        "status": "ready_for_safe_handoff",
        "tests_expected": "172 passed",
        "package": "docs/inventarios/projeto_automacao_homologacao_final_segura_20260605.zip",
        "security_controls_active": all(security["controls"].values()),
        "safe_endpoints": [
            "/api/v1/security/status",
            "/api/v1/security/real-mode-gate",
            "/api/v1/security/brain-review",
            "/api/v1/security/sandbox-readiness",
            "/api/v1/security/sandbox-execution-contract",
            "/api/v1/campaign-templates/hypothesis-test-01",
        ],
        "validation_commands": [
            "python -m pytest -p no:cacheprovider --basetemp .pytest_tmp",
            "cmd /c VALIDAR_PROJETO_FINAL.bat",
            "cmd /c VERIFICAR_PACOTE_FINAL.bat",
        ],
        "handoff_rules": [
            "Nunca expor .env, tokens ou credenciais no chat.",
            "Nunca ativar campanha, gasto ou active launch sem aprovacao humana explicita.",
            "Usar Brain/Brian antes de qualquer acao sensivel.",
            "Manter sandbox/test_account antes de producao.",
            "Manter campanha PAUSED no primeiro teste real controlado.",
        ],
        "blocked_until_user_approval": [
            "qualquer gasto real",
            "qualquer campanha ACTIVE",
            "qualquer alteracao real em conta principal",
            "qualquer exclusao de campanhas antigas",
        ],
        "sandbox_summary": {
            "status": sandbox["status"],
            "sandbox_ready": sandbox["sandbox_ready"],
            "production_ready": sandbox["production_ready"],
            "required_next_steps": sandbox["required_next_steps"],
        },
        "sandbox_approval_phrase": APPROVAL_PHRASE,
        "next_recommended_mission": "Configurar/validar sandbox Meta ou conta de anuncio separada sem gasto ativo.",
    }
