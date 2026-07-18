"""Diretor Criativo Viral: engenharia reversa de videos campeoes + blueprint.

Metodologia embutida (auditoria de 4 camadas):
1. Engenharia de Viralizacao (neuro-analise): hook, loop de retencao, causa raiz.
2. Arquitetura de Conversao: roteiro Hook -> Agitacao -> Solucao -> CTA.
3. Especificacoes Cinematograficas: cortes, ritmo, color grading, sound design.
4. Checklist de Ouro antes de postar.

Usa DeepSeek como motor. Sem chave, retorna o blueprint-template da metodologia.
"""

from __future__ import annotations

from typing import Any

from app.services.ad_library_real import deepseek_copy

SYSTEM_METHOD = """Voce e um Diretor Criativo e Estrategista Chefe de Performance no TikTok,
especialista em algoritmos e Copywriting de Resposta Direta. Missao: maximizar ROI com videos
que viralizam E convertem. Seja implacavel com qualidade; trate cada video como ativo financeiro.
Regras de ouro: ritmo frenetico com qualidade visual impecavel; NUNCA parecer anuncio obvio
(deve parecer conteudo organico); sempre priorizar Quebra de Padrao para vencer o algoritmo."""


def analyze_reference(
    reference: str,
    product: str,
    niche: str = "",
    objective: str = "VENDAS",
) -> dict[str, Any]:
    """Auditoria de Alta Performance em 4 camadas sobre um video de referencia."""
    prompt = f"""{SYSTEM_METHOD}

VIDEO DE REFERENCIA (link ou descricao): {reference}
MEU PRODUTO: {product}
NICHO: {niche or 'nao informado'}
OBJETIVO: {objective}

Realize o Relatorio de Desconstrucao de Performance EXATAMENTE nesta estrutura:

## CAMADA 1 - ENGENHARIA DE VIRALIZACAO
- HOOK: emocao exata explorada (vies cognitivo) e por que para o scroll
- LOOP DE RETENCAO: mapa de interesse, onde o espectador sairia e como o video evita
- CAUSA RAIZ: por que o algoritmo premiou este video

## CAMADA 2 - ARQUITETURA DE CONVERSAO (roteiro adaptado ao MEU produto)
- HOOK (0-3s): stop-scroll agressivo
- AGITACAO (3-10s): o problema sentido
- SOLUCAO (10-25s): produto como unica saida logica, sem parecer propaganda
- CTA (final): escassez ou ganho imediato

## CAMADA 3 - ESPECIFICACOES CINEMATOGRAFICAS
- DIRECAO DE ARTE: iluminacao, paleta, enquadramentos, transicoes
- PACING: duracao exata de cada corte
- SOUND DESIGN: SFX, batidas de transicao, tipo de trilha
- PROMPTS DE IA: prompt tecnico para gerar B-rolls (Runway/Kling) se necessario

## CAMADA 4 - CHECKLIST DE OURO
- [ ] Gancho para o scroll em menos de 1 segundo?
- [ ] Audio com fator de retencao?
- [ ] Transicao entretenimento->venda imperceptivel?

## PLANO DE ACAO - PROXIMOS 30 MINUTOS
Passo a passo executavel agora."""

    result = deepseek_copy(prompt)
    if result:
        return {"status": "ok", "engine": "deepseek", "report": result}
    return {
        "status": "partial",
        "engine": "template",
        "message": "DEEPSEEK_API_KEY nao configurada; segue o blueprint da metodologia para preencher manualmente.",
        "report": prompt,
    }


MARKETS = {
    "US": {"currency": "USD", "language": "en-US", "voice_lang": "en",
           "context": "mercado americano: ritmo agressivo, prova social com numeros, 'free shipping', urgencia direta"},
    "EU": {"currency": "EUR", "language": "es-ES", "voice_lang": "es",
           "context": "mercado europeu: tom mais sofisticado e confiavel, qualidade e garantia pesam mais que urgencia"},
    "BR": {"currency": "BRL", "language": "pt-BR", "voice_lang": "pt",
           "context": "mercado brasileiro: emocao, humor leve, 'frete rapido', Pix com desconto, prova social calorosa"},
}


def build_global_pack(product: str, niche: str = "", blueprint: str = "") -> dict[str, Any]:
    """Roteiro viral localizado para os 3 mercados (US/USD, EU/EUR, BR/BRL)."""
    pack: dict[str, Any] = {"status": "ok", "product": product, "markets": {}}
    for code, m in MARKETS.items():
        prompt = f"""{SYSTEM_METHOD}

PRODUTO: {product}
NICHO: {niche or 'dropshipping'}
MERCADO: {code} — moeda {m['currency']} — idioma do video: {m['language']}
CONTEXTO CULTURAL: {m['context']}
BLUEPRINT DE REFERENCIA (esqueleto vencedor a remodelar, sem copiar): {blueprint or 'antes/depois com prova visual + UGC organico'}

Escreva NO IDIOMA {m['language']} o roteiro de video TikTok de 30s no mais alto padrao viral local:
6 cenas no formato 'CENA N (Xs-Ys) | IMAGEM: ... | NARRACAO: ... | TEXTO NA TELA: ... | SOM: ...'
Precos e ofertas em {m['currency']}. Hook stop-scroll nativo da cultura local (nao traduzido ao pe da letra).
No final: NARRACAO_COMPLETA: (todas as falas juntas, no idioma {m['language']})."""
        result = deepseek_copy(prompt)
        pack["markets"][code] = {
            "currency": m["currency"],
            "language": m["language"],
            "engine": "deepseek" if result else "template",
            "script": result or prompt,
        }
    return pack


def build_viral_script(product: str, niche: str = "", angle: str = "") -> dict[str, Any]:
    """Roteiro viral completo cena a cena para o renderizador premium."""
    prompt = f"""{SYSTEM_METHOD}

PRODUTO: {product}
NICHO: {niche or 'dropshipping'}
ANGULO (opcional): {angle or 'escolha o mais forte'}

Escreva o ROTEIRO DE EDICAO cena a cena de um video TikTok de 30-40s que parece organico:

Para CADA cena (6 a 8 cenas):
CENA N (Xs-Ys) | IMAGEM: o que aparece (enquadramento, movimento de camera) | NARRACAO: fala exata |
TEXTO NA TELA: legenda curta em caixa alta | SOM: SFX/batida

Estrutura obrigatoria: Hook stop-scroll (0-3s) -> Agitacao -> Quebra de Padrao/Demonstracao ->
Prova social -> CTA com escassez. Narracao total de 80-100 palavras, energetica, em portugues do Brasil.
No final: NARRACAO_COMPLETA: (todas as falas juntas para o gerador de voz)."""

    result = deepseek_copy(prompt)
    if result:
        return {"status": "ok", "engine": "deepseek", "script": result}
    return {"status": "partial", "engine": "template",
            "message": "DEEPSEEK_API_KEY nao configurada.", "script": prompt}
