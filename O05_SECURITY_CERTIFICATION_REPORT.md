# O05 — SECURITY CERTIFICATION REPORT

Data UTC: 2026-06-25.

## Veredito O05

**O05 CONCLUÍDO COM RESSALVAS DOCUMENTADAS.** A suíte automatizada passa 3/3 vezes; a varredura textual não encontrou chaves reais pelos padrões procurados. Há endpoints Meta reais implementados no código, mas esta certificação não executou chamadas de rede contra Meta/TikTok.

## Comandos e evidências

```bash
python -m compileall -q src
# compileall: PASS
```

```bash
rg -n "(sk-[A-Za-z0-9_-]{20,}|EA[A-Za-z0-9]{20,}|xox[baprs]-|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})" . --glob '!data/**' --glob '!*.db' --glob '!*.sqlite' || true
```

Achados: somente strings sintéticas/test fixtures (`tools/ffmpeg`, `run_r12_e2e.sh`, `src/app/tests/test_secrets_policy.py`).

```bash
rg -n "graph\.facebook\.com|business-api\.tiktok|open\.tiktokapis\.com|ads\.tiktok\.com" src tests || true
```

Achados: `src/app/integrations/meta_marketing.py` e `src/app/services/capi_enterprise.py` constroem URLs Meta, mas nenhum teste desta rodada executou rede real contra esses destinos. Não há ocorrência TikTok em `src`.

## Ressalvas

- O workspace não tem remote configurado; não foi possível validar proteção de branch, secrets do GitHub ou status de PRs diretamente.
- A certificação é estática + suíte local, não pentest externo.
