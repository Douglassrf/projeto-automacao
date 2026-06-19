# C02_SITE_BUILDER_GUARD_FIX_REPORT.md — Missão corretiva C02 (Guard de aprovação humana no Site Builder)

Data: 2026-06-19. Origem: decisão da arquiteta após aprovar C01 — "libere C02 agora. Não coloque funcionalidade nova até C02–C07 terminarem."

## 1. O que estava errado

`POST /api/v1/site-builder/generate` (`src/app/api/routes/site_builder.py`) calculava o resultado de `site_publish_security_guard(...)` e devolvia ele no campo `security_guard` da resposta — mas **nunca verificava esse resultado**. Mesmo quando o guard retornava `status="blocked"`, a rota seguia chamando `SiteBuilderBridge().safe_generate(...)` e devolvia `200 OK` com o site gerado normalmente. O guard era decorativo.

Investigação adicional revelou um segundo problema, mais sutil: o schema `SiteGenerateRequest` (`src/app/schemas/site_builder.py`) **não declara nenhum campo `confirmed_by_user`**. Como o guard lê `payload.get("confirmed_by_user")` a partir de `payload.model_dump(mode="json")`, e o pydantic descarta silenciosamente qualquer campo não declarado no schema, esse valor é sempre `None`/`False` — ou seja, hoje **não existe nenhum jeito real de aprovar uma publicação não-dry-run através dessa rota**, mesmo que o chamador tente. Isso significa que, com a correção, qualquer pedido de publicação real (`deploy.dry_run=False`) é bloqueado por padrão, e fica assim até existir um mecanismo de aprovação separado e legítimo (fora do escopo de C02 — não é para criar funcionalidade nova agora).

## 2. Correção aplicada

Arquivo: `src/app/api/routes/site_builder.py` (39 → 83 linhas).

- O guard agora é a única fonte de verdade: se `guard["status"] == "blocked"`, a rota **levanta `HTTPException(403)`** com `blocked_reasons` e `requires_human_approval` no corpo do erro, e `SiteBuilderBridge().safe_generate(...)` **nunca é chamado** — nenhum arquivo de site é criado.
- Toda chamada (bloqueada ou permitida) é registrada no log de auditoria imutável existente (`app.services.observability.immutable_audit_event`, que grava em `logs/immutable_audit_events.log` com hash-chain), incluindo o ator autenticado (e-mail do usuário, via o `current_user` já exigido desde a C01), os motivos do bloqueio e os dados do pedido de deploy.
- Nenhum campo novo foi adicionado ao schema para "aprovar" a publicação — propositalmente, para não reabrir a brecha de autoaprovação via payload. Isso é uma decisão consciente de escopo: a arquitetura master pediu para não criar funcionalidade nova nesta fase; criar um fluxo de aprovação separado (ex.: um endpoint de aprovação dedicado, como o `agency-operator` já tem para workflows) é trabalho futuro, não parte de C02.

## 3. Teste — evidência real dos 3 critérios de aceite + auditoria

Arquivo novo: `src/app/tests/test_c02_site_builder_guard_enforced.py` (4 testes).

```
src/app/tests/test_c02_site_builder_guard_enforced.py::test_c02_payload_normal_dry_run_ainda_funciona PASSED
src/app/tests/test_c02_site_builder_guard_enforced.py::test_c02_payload_bloqueado_nao_gera_site PASSED
src/app/tests/test_c02_site_builder_guard_enforced.py::test_c02_tentativa_de_autoaprovacao_via_payload_falha PASSED
src/app/tests/test_c02_site_builder_guard_enforced.py::test_c02_guard_bloqueado_fica_registrado_no_audit_log_imutavel PASSED

4 passed, 1 warning in 8.71s
```

| Critério da missão | Teste | Resultado |
|---|---|---|
| Payload normal funciona | `test_c02_payload_normal_dry_run_ainda_funciona` — `deploy.dry_run=True` (caminho usado por todas as missões R) | `200`, `security_guard.status == "ok"`, site gerado normalmente |
| Payload bloqueado não gera site | `test_c02_payload_bloqueado_nao_gera_site` — `deploy.dry_run=False`, sem nenhuma aprovação | `403`, `blocked_reasons` contém `human_approval_required`, **nenhum arquivo criado no disco** (verificado vasculhando o diretório de saída) |
| Tentativa de burlar aprovação falha | `test_c02_tentativa_de_autoaprovacao_via_payload_falha` — mesmo payload bloqueado, mas com `"confirmed_by_user": true` injetado manualmente no corpo da requisição (raiz e dentro de `deploy`) | Continua `403` — o campo extra é descartado pelo pydantic antes de chegar ao guard, prova de que a autoaprovação via payload não funciona |
| Registrar audit log | `test_c02_guard_bloqueado_fica_registrado_no_audit_log_imutavel` | Evento `site_builder.generate.blocked` aparece no log imutável, e a cadeia de hash (`ImmutableAuditLog.verify()`) continua **válida** depois do evento (sem corrupção) |

## 4. Suíte de regressão completa

```
265 passed, 1 warning in 24.84s
```

261 testes anteriores (pós-C01) + 4 testes novos da C02 = 265, **zero falhas, zero regressões**. As duas rotas pré-existentes que usam `deploy.dry_run=True` (`test_site_builder.py`) continuam passando sem alteração — confirmando que o caminho normal (o único usado em todas as missões R até agora) não foi afetado.

## 5. Achado colateral (ambiente, não é bug de código)

Ao tentar confirmar a edição via `git diff` no mount Linux deste sandbox, o arquivo apareceu truncado em 26 linhas (contra as 83 linhas reais, confirmadas pela ferramenta de edição e pela cópia espelhada usada nos testes). Mesma desincronização de mount já documentada nas missões R11 e C01 — não afeta o código real, só a visibilidade do `git`/`bash` neste sandbox imediatamente após uma edição. Recomendação mantida: sempre conferir via `touch` + `git update-index --refresh` (ou simplesmente aguardar/reabrir) antes de confiar em `git status`/`git diff` para arquivos editados na mesma sessão.

## 6. Status final

**MISSÃO C02: CONCLUÍDA COM EVIDÊNCIA REAL.**

- Guard agora bloqueia de fato — execução para antes de gerar/publicar.
- Erro controlado (403 com motivo), não um 500 nem um 200 mascarado.
- Audit log imutável registra a tentativa, cadeia de hash íntegra.
- Autoaprovação via payload comprovadamente impossível (campo extra é ignorado pelo schema).
- 265/265 testes passando.

Nenhuma funcionalidade nova foi criada — apenas a aplicação real de um guard que já existia. Pronto para liberar C03.
