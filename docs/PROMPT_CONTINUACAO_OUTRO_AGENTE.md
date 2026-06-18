# Prompt De Continuacao Para Outro Agente

Use este arquivo para continuar o Projeto Automacao sem gastar tokens com historico antigo.

## Contexto Curto

Projeto: AdIntelligence Pro / Projeto Automacao.

Status:

```txt
SAFE E2E HOMOLOGATED
```

O projeto foi concluido e homologado em modo seguro ponta a ponta. A escrita real na Meta ficou fora do fluxo principal porque a propria Meta bloqueou modificacoes na conta.

## Regras Obrigatorias

- Nao expor `.env`, token ou credenciais.
- Nao ativar gasto real sem autorizacao literal do usuario.
- Nao criar campanha ativa.
- Nao deletar campanhas antigas enquanto a Meta continuar bloqueando.
- Operar em modo economico: ler arquivos chave, fazer patch pequeno, validar.
- Usar Cerebro/Brian como memoria, decisao e aprendizado.

## Arquivos Para Ler Primeiro

1. `docs/GUIA_OPERACIONAL_FINAL.md`
2. `docs/CHECKLIST_CONCLUSAO_PROJETO.md`
3. `docs/ROTINA_OPERACIONAL_DIARIA.md`
4. `docs/RELATORIO_ENTREGA_FINAL.md`
5. `docs/PROXIMOS_PASSOS.md`
6. `docs/historico_missoes/RELATORIO_HOMOLOGACAO_FINAL_SEGURA.md`

## Validacao Rapida

```bat
VALIDAR_PROJETO_FINAL.bat
```

Ou:

```bash
python -m pytest src/app/tests/test_final_safe_e2e.py -p no:cacheprovider --basetemp .pytest_tmp
```

## Rodar API

```bat
INICIAR_PROJETO_FINAL.bat
```

Abrir:

```txt
http://127.0.0.1:8000/docs
```

## Pacote Final

```txt
docs/inventarios/projeto_automacao_homologacao_final_segura_20260605.zip
```

SHA256: consultar o arquivo externo `.zip.sha256` ao lado do pacote.

## Proximo Trabalho Recomendado

Se o usuario quiser continuar:

1. Criar sandbox/conta separada Meta, se possivel.
2. Completar conjunto/anuncio Codex real pausado apenas com autorizacao especifica.
3. Manter `META_ALLOW_ACTIVE_LAUNCH=false`.
4. Validar tudo em `dry_run` antes de qualquer escrita real.

Frase minima para proxima acao real pausada:

```txt
Autorizo continuar a campanha PAUSADA com orçamento de R$ 6 por dia, sem ativar gasto.
```
