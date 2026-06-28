"""Domínio: Technical Knowledge Base (Missão 73)."""

from pydantic import BaseModel


class TechnicalKnowledgeConfig(BaseModel):
    # Missao 73 - Technical Knowledge Base: quando True (padrao), referencias
    # cruzadas doc↔codigo aparecem na base de conhecimento. Nunca deve ser
    # False em producao.
    technical_knowledge_include_cross_references: bool = True
    technical_knowledge_include_draft_adrs: bool = True
    technical_knowledge_include_draft_modules: bool = True
