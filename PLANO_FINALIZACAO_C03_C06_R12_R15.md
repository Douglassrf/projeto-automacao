# PLANO_FINALIZACAO_C03_C06_R12_R15.md — Plano mestre para concluir o projeto ponta-a-ponta

Data: 2026-06-19. Status no momento deste plano: R01-R11 + C01 + C02 concluídos, testados e versionados em `origin/master` (commits `c44bea6` e `45181dd`). Faltam 8 missões para fechar o projeto raiz: **C03, C04, C05, C06, R12, R13, R14, R15**.

## 1. Por que dividir com Codex agora

R01-C02 foram feitos em sequência, um agente só, porque cada correção dependia de entender o estado real do código (auditoria de autenticação, guard ignorado, mount corrompido). A partir de C03 as missões restantes são **mais independentes entre si** — dá para paralelizar sem dois agentes pisarem no mesmo arquivo ao mesmo tempo. Objetivo: terminar mais rápido sem abrir mão do padrão de evidência real que já está estabelecido (mesma regra de sempre: **não avançar sem evidência real**, segredo nunca em texto puro, nunca tocar flag real da Meta ou `AUTH_REQUIRED` sem autorização explícita do Douglas).

## 2. Inventário das 8 missões restantes

| # | Missão | Escopo (a partir do código já investigado) |
|---|---|---|
| C03 | Aplicar guard de IA pesada/vídeo | `src/app/api/routes/video_pipeline.py` já tem `Depends(get_current_user)` (corrigido na C01), mas o `ai_heavy_security_guard(...)` é calculado e **ignorado**, mesmo padrão de bug exato da C02 (guard decorativo). Precisa bloquear de fato com 403 antes de qualquer processamento pesado/de vídeo. |
| C04 | Proteger credenciais Meta (sandbox vs produção) | Já existe infraestrutura real: `core/meta_sandbox_setup.py`, `core/real_mode_gate.py`, `core/secrets_policy.py`, `core/sandbox_execution_contract.py`, settings `meta_env`, `meta_allow_active_launch`, `meta_allow_production_real`. C04 é **auditar essa infraestrutura de ponta a ponta** e fechar qualquer brecha onde uma chamada destinada a sandbox possa vazar para a conta de produção (ex.: validar que `meta_env=sandbox` é checado em todo caminho que toca a Meta, não só nos endpoints "de preparo"). |
| C05 | Teste Meta real isolado (conta sandbox) | R11 ficou **bloqueada por falta de conta de teste dedicada** (ver `META_REAL_TEST_REPORT.md`, seção final: "abrir uma conta de anúncios sandbox/teste dedicada na Meta... isso já está refletido na missão corretiva C05"). Precisa de uma conta de teste Meta (Business Manager → Contas de teste) com credenciais **isoladas e não-produtivas**, fornecidas pelo Douglas, antes de qualquer chamada real. |
| C06 | Revalidar Python 3.11+ e suíte pytest completa | Confirmar versão mínima do Python suportada de fato (checar `pyproject.toml`/`runtime`/sintaxe usada) e rodar a suíte completa (`265+` testes) como gate final pós C03-C05. |
| R12 | Teste do fluxo completo (FULL_ROOT_E2E_REPORT.md) | Rodar o pipeline completo numa única execução contínua (upload → mineração → inteligência → site → criativos → vídeo → TikTok → Meta dry-run) — diferente de R02-R11, que testaram cada etapa isolada. |
| R13 | Teste de falhas (FAILURE_TEST_REPORT.md) | Injeção de falha em cada etapa (dependência indisponível, input inválido, timeout) verificando que o sistema falha de forma controlada (erro claro, sem 500 vazando stack trace/segredo). |
| R14 | Teste de segurança final (SECURITY_FINAL_TEST_REPORT.md) | Auditoria de segurança fim-a-fim: toda rota sensível com auth (C01), todo guard de fato bloqueando (C02/C03), nenhum segredo em log/auditoria, `.env.example` sem valor real, dependências sem CVE conhecida. |
| R15 | Homologação final + entrega (ROOT_E2E_FINAL_REPORT.md) | Consolidação de tudo (R01-R14 + C01-C06) num relatório final único de homologação e entrega. |

> Não existe uma "C07" com ticket próprio — só C01 a C06 estão de fato no backlog rastreado. Se houver algo específico que o Douglas tinha em mente como C07, está faltando o conteúdo dessa missão; sinalizar se for o caso.

## 3. Critério de divisão (não é 50/50 cego — é por risco e continuidade)

**Fico com (Claude): C04, C05, R12, R15.**
**Vai para o Codex: C03, C06, R13, R14.**

Por quê:

- **C04 e C05 tocam credencial real da Meta** (mesmo que de conta de teste/sandbox, ainda é integração real com dinheiro potencialmente em jogo se mal configurada). As regras de segurança desta missão inteira — nunca virar flag real, nunca expor segredo, nunca arriscar chamada de produção — estão acumuladas no contexto desta sessão. Passar isso para uma sessão nova do Codex sem o mesmo histórico é risco desnecessário quando a alternativa (eu mesmo fazer) já está calibrada.
- **R12 e R15 são integração final** — precisam de visão completa de tudo que foi corrigido (R01-C06), inclusive o que o Codex vai produzir. Fazem mais sentido ficando com quem está acompanhando o histórico inteiro, para não homologar algo sem saber o que mudou.
- **C03, C06, R13, R14 são mecânicos e bem especificados**: C03 é literalmente o mesmo padrão de bug já corrigido na C02 (replicar a receita). C06 é ambiente/ferramental, sem segredo. R13 e R14 são auditorias guiadas por checklist, executáveis com credenciais 100% sintéticas/isoladas — não precisam tocar nada real da Meta.

## 4. Fases e dependências

```
FASE 1 (paralelo, sem dependência entre si)
  Codex → C03 (guard de vídeo/IA pesada)
  Claude → C04 (auditoria de credenciais Meta sandbox vs produção)

FASE 2 (paralelo, após Fase 1)
  Codex → C06 (Python 3.11+ + suíte pytest completa, já incluindo o fix da C03)
  Claude → C05 (teste Meta real isolado em conta sandbox — depende da auditoria da C04 estar limpa)

FASE 3 (paralelo)
  Codex → R13 (teste de falhas)
  Claude → R12 (fluxo completo E2E)

FASE 4 (fechamento)
  Codex → R14 (segurança final, usando checklist fornecido — não precisa de credencial real)
  Claude → R15 (homologação final + entrega, consolidando tudo, inclusive o trabalho do Codex)
```

## 5. Regras inegociáveis (valem para as duas metades)

1. Não avançar para a próxima missão sem evidência real (output de teste real, não simulado/mockado apresentado como se fosse real).
2. Nenhum segredo (token, senha, chave) em texto puro em relatório, log ou commit — só presença/ausência, nunca o valor.
3. Nunca alterar `META_DRY_RUN`, `META_AUTOPUBLISH`, `META_ALLOW_ACTIVE_LAUNCH`, `META_ALLOW_PRODUCTION_REAL` ou `AUTH_REQUIRED` no `.env` real sem autorização explícita do Douglas.
4. Nunca arriscar chamada de rede real para a Meta fora do escopo explicitamente autorizado da C05 (e mesmo essa, só contra conta de teste/sandbox, nunca a conta principal).
5. Nenhuma funcionalidade nova até C03-C06 estarem 100% concluídas (mesma regra que já valeu para C01/C02).
6. Verificar integridade de arquivo editado antes de confiar em `git diff`/`git status` neste tipo de ambiente — já tivemos 6+ casos de mount/cache desatualizado mascarando o conteúdo real nesta sessão. `ast.parse` sozinho não é suficiente (já provou ser insuficiente uma vez); comparar conteúdo byte-a-byte com uma cópia confiável quando houver dúvida.

## 6. Padrão de evidência exigido por missão

Mesmo formato dos relatórios já entregues (`C01_AUTH_FIX_REPORT.md`, `C02_SITE_BUILDER_GUARD_FIX_REPORT.md`): o que estava errado, correção aplicada (arquivo + diff), teste novo com saída real colada (não resumida, não "passou" sem prova), suíte de regressão completa rodando no final, achados colaterais registrados por transparência mesmo que fora do escopo.

## 7. Status de execução

- [ ] C03 (Codex)
- [ ] C04 (Claude) — próxima ação imediata
- [ ] C05 (Claude)
- [ ] C06 (Codex)
- [ ] R12 (Claude)
- [ ] R13 (Codex)
- [ ] R14 (Codex)
- [ ] R15 (Claude)
