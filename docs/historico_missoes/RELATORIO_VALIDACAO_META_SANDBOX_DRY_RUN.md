# Relatorio - Validacao Meta Sandbox Dry-Run

Data: 2026-06-04

## Objetivo

Validar o sistema com token Meta configurado, sem gasto, sem publicacao e sem campanha ativa criada pelo projeto.

## Configuracao Validada

```txt
META_ENV=sandbox
META_ACCESS_TOKEN=<set>
META_AD_ACCOUNT_ID=113923608813145
META_PAGE_ID=187294135128232
META_PIXEL_ID=966191649729251
META_DRY_RUN=true
META_AUTOPUBLISH=false
META_ALLOW_PRODUCTION_REAL=false
```

## Leitura Segura Da Meta

Conta lida via Graph API em modo somente leitura:

```txt
Conta: Douglas Oliver
Moeda: BRL
Fuso: America/Sao_Paulo
Status da conta: 1
```

Tambem foi detectado que existem campanhas ativas reais na conta. Nenhuma delas foi alterada.

Pixel de teste criado:

```txt
Nome: AdIntelligence Pro Test Pixel
ID: 966191649729251
```

## Dry-Run Executado

Resultado do operador:

```txt
launch_dry_run: true
launch_attempted: 4
launch_published: 0
launch_blocked: 0
pixel_id: 966191649729251
rollback_status: dry_run_ready
monitor_status: ok
monitor_alerts: 0
```

## Guardrails Mantidos

- Nenhuma publicacao real.
- Nenhum gasto.
- Nenhuma campanha real criada.
- Nenhuma campanha ativa alterada.
- Autopublish desligado.
- Producao principal bloqueada.
- `.env` protegido por `.gitignore`.
- ZIP homologado sem `.env`.

## Testes

```txt
99 passed, 1 warning
```

## Pendencia Para Producao Real

```txt
Aprovacao humana final
META_DRY_RUN=false
META_AUTOPUBLISH=true
Campanha criada primeiro como PAUSED
```

Proximo passo seguro: executar readiness final e criar campanha pausada somente se o usuario aprovar explicitamente.
