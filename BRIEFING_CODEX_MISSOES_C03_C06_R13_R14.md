# BRIEFING_CODEX_MISSOES_C03_C06_R13_R14.md — Ordem de missão para o Codex

Para: Codex. De: Claude (co-responsável pela finalização do projeto, junto com o Douglas). Data: 2026-06-19.

Leia este documento inteiro antes de tocar em qualquer arquivo. O padrão de qualidade aqui não é negociável: este projeto já passou por uma auditoria técnica formal ("APROVADO COM RESSALVAS CRÍTICAS") e por 13 missões com evidência real (R01-R11, C01, C02) já mescladas em `origin/master` (commits `c44bea6`, `45181dd`). Você está entrando numa esteira que já tem um padrão de excelência estabelecido — siga-o, não reinvente.

## 0. Contexto do projeto

Sistema de automação de campanhas (mineração de anúncios → inteligência → geração de site → criativos → vídeo → publicação TikTok/Meta). Stack: FastAPI + SQLite + pytest. Há um histórico documentado de bugs do tipo "guard calculado mas nunca aplicado" (a rota computa um resultado de segurança e devolve no JSON, mas segue executando a ação mesmo quando o guard diz para bloquear). Já corrigimos esse padrão exato uma vez (missão C02, arquivo `C02_SITE_BUILDER_GUARD_FIX_REPORT.md` — leia esse relatório inteiro antes de começar a C03, é literalmente o molde a seguir).

## 1. Regras inegociáveis — leia antes de qualquer linha de código

1. **Não avançar sem evidência real.** Nenhuma missão é considerada concluída sem saída de teste real colada no relatório (não resumo, não "passou" sem prova, não teste que mocka o próprio critério de aceite).
2. **Nenhum segredo em texto puro.** Token, senha, chave de API, connection string — nunca aparecem em relatório, log, commit ou saída de terminal copiada. Só "presente"/"ausente", nunca o valor. Use sempre credenciais sintéticas/isoladas em teste (`Settings(_env_file=None, ...)` com valores fake, nunca leia o `.env` real).
3. **Nunca toque flags reais.** `META_DRY_RUN`, `META_AUTOPUBLISH`, `META_ALLOW_ACTIVE_LAUNCH`, `META_ALLOW_PRODUCTION_REAL`, `AUTH_REQUIRED` no `.env` real do projeto não podem ser alterados, nem para teste, nem "temporariamente". Se uma missão sua tocar nessas flags, isole tudo em settings/env sintéticos, nunca no `.env` real.
4. **Nenhuma chamada de rede real para a Meta.** Nenhuma das suas 4 missões (C03, C06, R13, R14) deveria, em nenhum momento, fazer uma chamada de rede real contra a API da Meta. Se algum teste seu chegar perto disso, pare e use a técnica de "tripwire de rede" (ver seção 5).
5. **Nenhuma funcionalidade nova.** Você está corrigindo e auditando o que já existe — não adicionar endpoint novo, campo novo, feature nova. Se achar que falta algo, registre como achado para decisão do Douglas, não implemente.
6. **Verifique integridade de arquivo antes de confiar no que seu ambiente mostra.** Esta sessão já encontrou 6+ casos de mount/cache mostrando conteúdo desatualizado/truncado de forma que passava despercebido até em `ast.parse`. Depois de editar um arquivo, releia o conteúdo final e confirme que é o que você esperava antes de seguir.

## 2. Suas 4 missões

### C03 — Aplicar guard de IA pesada/vídeo

**O que investigar primeiro:** `src/app/api/routes/video_pipeline.py`. Confirme onde `ai_heavy_security_guard(...)` (ou nome equivalente — procure por "guard" nesse arquivo e no diretório `src/app/core/`) é chamado. Praticamente certo que, como na C02, o resultado do guard é calculado e devolvido na resposta, mas a rota segue executando a geração/processamento pesado mesmo quando o guard indica bloqueio.

**Correção esperada (mesmo padrão da C02):** se o guard retornar bloqueio, levantar `HTTPException(403)` com os motivos do bloqueio **antes** de qualquer processamento pesado, registrar no log de auditoria imutável (`app.services.observability.immutable_audit_event`), e garantir que nenhum arquivo de vídeo/recurso pesado seja gerado quando bloqueado.

**Critério de aceite:**
- Payload normal (sem bloqueio) continua funcionando — zero regressão.
- Payload que deveria ser bloqueado → 403, nada é gerado no disco.
- Tentativa de auto-aprovação via campo extra no payload (campo não declarado no schema) continua bloqueada.
- Evento registrado no audit log imutável, cadeia de hash continua válida depois.
- Escreva o teste novo no padrão de `src/app/tests/test_c02_site_builder_guard_enforced.py` (4 cenários equivalentes).

**Entregável:** `C03_VIDEO_AI_GUARD_FIX_REPORT.md` no mesmo formato do `C02_SITE_BUILDER_GUARD_FIX_REPORT.md`.

### C06 — Revalidar Python 3.11+ e suíte pytest completa

**O que fazer:**
1. Confirmar a versão mínima de Python realmente suportada pelo código (checar uso de sintaxe/features específicas de versão, `pyproject.toml`/configuração de runtime existente, imports condicionais). Se houver incompatibilidade com 3.11+, documentar e corrigir.
2. Rodar a suíte completa de testes (`pytest src/app/tests/ -q`) **depois** que C03 estiver mesclado, para já validar tudo junto. Meta atual antes da C03: 265 passed. Depois da C03, deve continuar 100% verde com os testes novos somados.
3. Se o ambiente de execução for lento/instável contra um mount de rede (sintoma: testes simples travando, sem erro de lógica), use uma cópia local rápida do repositório para rodar a suíte — não é bug de código, é I/O do ambiente. Documente se isso ocorrer.

**Critério de aceite:** suíte 100% verde, versão Python confirmada e documentada, zero teste pulado/silenciado sem justificativa.

**Entregável:** `C06_PYTHON_PYTEST_REVALIDATION_REPORT.md`.

### R13 — Teste de falhas (FAILURE_TEST_REPORT.md)

**O que fazer:** para cada etapa principal do pipeline (upload, mineração, inteligência, geração de site, criativos, vídeo, TikTok), simular pelo menos um cenário de falha real:
- dependência externa indisponível (timeout, erro de conexão simulado — nunca uma chamada de rede real, sempre via monkeypatch/mock da camada de transporte);
- input inválido/malformado;
- recurso ausente (arquivo não encontrado, registro inexistente).

**Critério de aceite:** em todos os cenários, o sistema responde com erro controlado (4xx/5xx com mensagem clara), nunca expõe stack trace com caminho de arquivo sensível ou segredo, nunca trava indefinidamente, nunca deixa estado inconsistente (ex.: arquivo parcialmente escrito sem registro do erro).

**Entregável:** `FAILURE_TEST_REPORT.md`.

### R14 — Teste de segurança final (SECURITY_FINAL_TEST_REPORT.md)

**Checklist mínimo a executar (cada item precisa de evidência, não de "ok" sem prova):**
1. Toda rota que expõe dado sensível ou aciona ação de negócio tem `Depends(get_current_user)` — revalidar a lista da C01 mais qualquer rota nova/alterada desde então.
2. Todo guard de segurança (C02, C03) bloqueia de fato quando deveria — não só calcula o resultado.
3. Nenhum segredo aparece em `logs/`, no log de auditoria imutável, ou em qualquer resposta de API (grep por padrões de token/chave em respostas de teste).
4. `.env.example` não contém nenhum valor real, só placeholders.
5. Dependências do projeto sem CVE crítica conhecida (`pip-audit` ou equivalente, se disponível no ambiente).
6. Nenhuma flag de produção da Meta pode ser ativada por payload de requisição (sempre vem de configuração de servidor, nunca de input do cliente).

**Importante:** este checklist é executável inteiramente com credenciais sintéticas/isoladas — não precisa e não deve tocar nenhuma credencial real da Meta.

**Entregável:** `SECURITY_FINAL_TEST_REPORT.md`.

## 3. Técnica de "tripwire de rede" (use sempre que testar algo perto de uma chamada real)

Faça monkeypatch de `httpx.get`/`post`/`delete` (ou da função de transporte equivalente) para levantar uma exceção imediata e clara (`NetworkTripwireError` ou nome similar) se qualquer código tentar de fato sair para a rede. Isso prova que o caminho testado nunca alcança a rede, sem nunca arriscar uma chamada real. Veja `test_meta_guardrails_isolated_R11.py` (raiz do repo) como referência de implementação.

## 4. Como entregar

- Um relatório `.md` por missão, no mesmo padrão dos já existentes (seções: o que estava errado, correção aplicada, teste com saída real colada, suíte de regressão completa, achados colaterais).
- Commits separados por missão, mensagem clara em português, sem nenhum valor de segredo no diff.
- Ao terminar as 4, sinalize para o Douglas/Claude para entrarmos na R15 (homologação final), que vai consolidar o seu trabalho junto com C04/C05/R12.

## 5. Padrão de excelência exigido

Isto não é "deixar passar" — é entregar no mesmo nível do que já foi feito: investigação real antes de qualquer fix, teste que prova o critério de aceite (não que só não falha), suíte completa rodando no final, e total transparência sobre qualquer limitação do ambiente encontrada pelo caminho. Qualidade de engenheiro sênior, sem atalho, sem "deveria funcionar" sem prova.
