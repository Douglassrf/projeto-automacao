"""Domínio: auditoria de dependências (Missão 49)."""

from pydantic import BaseModel


class DependencyAuditConfig(BaseModel):
    # Missao 49 - Auditoria de Dependencias: quando True (padrao), uma
    # dependencia declarada em requirements.txt sem versao fixa (==)
    # aparece na lista de "issues" do endpoint /dependency-audit/* (nao so
    # na lista bruta de dependencias). Nunca deve ser False em producao.
    dependency_audit_warn_on_unpinned: bool = True
