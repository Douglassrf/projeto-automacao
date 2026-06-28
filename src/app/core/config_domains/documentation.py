"""Domínio: documentação viva (Missão 48)."""

from pydantic import BaseModel


class DocumentationConfig(BaseModel):
    # Missao 48 - Documentacao Viva: por padrao, qualquer endpoint de
    # documentacao viva redige (oculta) o valor real de campos que
    # parecem segredo (token/senha/chave/secret no nome) em vez de
    # devolver o valor real. Nunca deve ser False em producao.
    documentation_redact_secrets: bool = True
