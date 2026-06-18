# Rotina Operacional Diaria

Data: 2026-06-05

## Objetivo

Operar o Projeto Automacao em modo seguro, economico e produtivo, sem depender do historico do chat.

## Inicio Do Dia

1. Abrir `docs/GUIA_OPERACIONAL_FINAL.md`.
2. Confirmar `docs/PROXIMOS_PASSOS.md`.
3. Confirmar que `.env` existe apenas no ambiente local e nunca sera enviado.
4. Rodar validacao curta:

```bat
VALIDAR_PROJETO_FINAL.bat
```

Ou:

```bash
python -m pytest src/app/tests/test_final_safe_e2e.py -p no:cacheprovider --basetemp .pytest_tmp
```

## Subir API

```bash
cd src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Ou:

```bat
INICIAR_PROJETO_FINAL.bat
```

Abrir:

```txt
http://127.0.0.1:8000/docs
```

## Checagens Rapidas

```txt
GET /
GET /api/v1/campaign-operator/status
GET /api/v1/campaign/dry-run/mock
```

Resultados esperados:

- API: `safe-runtime`
- Operador Meta: `dry_run=true`
- Autopublish: `false`
- Active launch: `false`
- Dry-run mock: `dry_run_ok`

## Regras De Meta

- Nao deletar campanhas antigas enquanto a Meta seguir bloqueando a conta.
- Nao ativar campanha.
- Nao alterar orcamento real sem frase de autorizacao especifica.
- Usar campanha Codex existente apenas com `existing_campaign_id=52616252576068`.

## Frase Exigida Para Proxima Acao Real Pausada

```txt
Autorizo continuar a campanha PAUSADA com orçamento de R$ 6 por dia, sem ativar gasto.
```

## Fechamento Do Dia

1. Rodar suite completa quando houver mudanca em codigo:

```bash
python -m pytest -p no:cacheprovider --basetemp .pytest_tmp
```

2. Atualizar relatorio em `docs/historico_missoes/`.
3. Regenerar ZIP final sem `.env`.
4. Conferir que o ZIP nao tem:

- `.env`
- banco local
- logs
- caches
- binarios grandes
