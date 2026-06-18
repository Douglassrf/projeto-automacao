# Relatorio Missao 35D - Zero Trust Internal Calls

Data: 2026-06-05

## Objetivo

Criar um contrato de seguranca para chamadas internas entre agentes e servicos, evitando confianca implicita entre modulos.

## Entregas

- `src/app/core/zero_trust.py`
- `src/app/tests/test_zero_trust_internal_calls.py`

## Regras Implementadas

- origem deve ser uma Service Account registrada.
- destino deve ser uma Service Account registrada.
- permissao deve existir no papel da origem.
- `correlation_id` e obrigatorio e deve seguir padrao rastreavel.
- `execution_id` e obrigatorio.
- `mission_id` e obrigatorio.
- escopo deve ser permitido para origem e destino.
- toda chamada valida gera envelope auditavel.

## Envelope Zero Trust

Campos obrigatorios:

- `source`
- `source_role`
- `target_service`
- `target_role`
- `permission`
- `scope`
- `origin`
- `correlation_id`
- `execution_id`
- `mission_id`
- `payload_summary`

## Validacao

```txt
test_zero_trust_internal_calls.py: 6 passed
suite completa: 123 passed
```

## Status

```txt
MISSAO 35D CONCLUIDA
PROXIMA MISSAO: 35E AUDIT LOG IMUTAVEL
```
