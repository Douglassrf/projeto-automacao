# Missão 82 — CI/CD Stabilization

Estabiliza pipeline CI/CD, corrige testes flaky (M43 LRU, M57 timeline),
adiciona job Windows com skip ffmpeg. CONFIG **3.1.0**.
Branch: `missao-82-ci-cd-stabilization`.

## Endpoints

- `GET /api/v1/ci-stabilization/live`
- `GET /api/v1/ci-stabilization/markdown`

## Alterações CI

- `ci.yml`: job Linux (ffmpeg) + job Windows (`pytest -m "not ffmpeg"`)
- `pytest.ini`: marker `ffmpeg`
- `conftest.py`: skip automático ffmpeg no Windows CI

## Evidência de testes

```text
$ pytest src/app/tests/test_m82_ci_cd_stabilization.py -q
8 passed in 3.36s
```
