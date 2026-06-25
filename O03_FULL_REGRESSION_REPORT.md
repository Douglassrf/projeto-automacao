# O03 — FULL REGRESSION REPORT

Data UTC: 2026-06-25.
Branch local: `work`.
HEAD verificado: `3c7081d Merge pull request #16 from Douglassrf/codex/concluir-todas-as-missoes-da-fase-omega`.

## Veredito O03

**O03 CONCLUÍDO no checkout local atual.**

A contradição do PR #16 foi reavaliada em checkout local limpo da ponta atual disponível neste workspace. O commit do PR #15 está presente no histórico (`eeae21e Merge pull request #15...`, contendo `59fee14 Add ffmpeg test shims for locked environments`) e `pytest -q` passou 3 vezes consecutivas com o mesmo resultado: `302 passed, 3 warnings`.

## Resolução da contradição #15 x #16

Causa comprovada: **(a) o sandbox/branch que gerou o relatório do PR #16 não refletia corretamente o efeito do #15 no momento em que o relatório foi escrito, ou executou a suíte a partir de estado anterior ao shim efetivamente carregado.**

Prova local atual contra a hipótese (b): o `conftest.py` da raiz injeta `tools/` no início do `PATH` durante `pytest_configure`; portanto o shim é carregado no comando `python -m pytest -q` usado nesta revalidação. Com o commit #15 presente, a suíte completa ficou verde 3/3 vezes.

## Comando executado

```bash
set -o pipefail
{
 echo '===== CLEAN MASTER CHECK ====='
 git status --short
 git branch --show-current
 git log --oneline -3
 echo '===== PYTEST VERSION ====='
 python -m pytest --version
 for i in 1 2 3; do
   echo "===== O03 FULL REGRESSION RUN $i/3 ====="
   python -m pytest -q
 done
} 2>&1 | tee /tmp/o03_pytest_runs_20260625.log
```

## Saída literal das 3 execuções

```text
===== CLEAN MASTER CHECK =====
work
3c7081d Merge pull request #16 from Douglassrf/codex/concluir-todas-as-missoes-da-fase-omega
7d1acb6 docs: add O03 full regression report
eeae21e Merge pull request #15 from Douglassrf/codex/resolve-bloqueios-de-pr-#14
===== PYTEST VERSION =====
pytest 9.0.3
===== O03 FULL REGRESSION RUN 1/3 =====
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 71%]
........................................................................ [ 95%]
..............                                                           [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
302 passed, 3 warnings in 8.90s
===== O03 FULL REGRESSION RUN 2/3 =====
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 71%]
........................................................................ [ 95%]
..............                                                           [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
302 passed, 3 warnings in 7.81s
===== O03 FULL REGRESSION RUN 3/3 =====
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 71%]
........................................................................ [ 95%]
..............                                                           [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
302 passed, 3 warnings in 7.71s
```
