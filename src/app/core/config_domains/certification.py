"""Domínio: certificação Platinum v1.3 (Missão 50)."""

from pydantic import BaseModel


class CertificationConfig(BaseModel):
    # Missao 50 - Certificacao Platinum v1.3: quando True (padrao), o
    # endpoint /certification/platinum so pode reportar
    # platinum_certified=True quando diagnosticos/alertas/auditoria de
    # dependencias estiverem todos limpos (gate "fail-closed"). Quando
    # False, o gate fica sempre fechado (platinum_certified=False),
    # mesmo que tudo esteja saudavel - desligar a exigencia nao deveria
    # nunca resultar em uma certificacao "de gracinha". Nunca deve ser
    # False em producao.
    certification_platinum_require_clean_diagnostics: bool = True
