# Relatorio - Perfis Meta Sandbox/Test Account/Production

Data: 2026-06-04

## Objetivo

Permitir teste real primeiro fora da conta principal, usando `sandbox` ou uma conta de anuncio separada antes de liberar `production`.

## Implementado

- Configuracao `META_ENV=sandbox|test_account|production`.
- Configuracao `META_ALLOW_PRODUCTION_REAL=false` por padrao.
- Status do operador agora mostra o ambiente Meta ativo.
- Readiness, credential review, assisted gate, hardening e launch validam o perfil.
- `META_ENV=production` bloqueia launch real sem `META_ALLOW_PRODUCTION_REAL=true`.
- `.env.example` atualizado.

## Fluxo recomendado

```txt
META_ENV=sandbox
↓
META_ENV=test_account
↓
META_ENV=production somente com aprovacao final
```

## Testes

```txt
src/app/tests/test_meta_environment_profiles.py: 2 passed
Suite completa: 99 passed
```

## Status

```txt
META ENV PROFILES VALIDADO
PRODUCAO PRINCIPAL BLOQUEADA POR PADRAO
PRIMEIRO TESTE REAL DEVE USAR SANDBOX OU TEST_ACCOUNT
```
