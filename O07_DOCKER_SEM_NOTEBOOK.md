# O07 sem Docker no notebook (8 GB RAM)

## Por que app.docker.com NÃO substitui o Docker Desktop

| O que é | O que faz |
|---------|-----------|
| **app.docker.com** (sua conta) | Login, Hub, imagens guardadas |
| **Docker Desktop** | Motor que roda `docker build` no PC |
| **Site no browser** | **Não executa** `verificar_docker_O07.sh` |

Abrir o Docker no internet = **conta e repositório de imagens**.  
O script O07 precisa de um **motor Docker** — local (pesado) ou **na nuvem**.

## Solução recomendada: GitHub Actions (0800)

O Docker roda nos servidores do GitHub — **zero RAM no seu notebook**.

### Passo 1 — Enviar o workflow (1x)

No PC, com internet:

```cmd
cd %USERPROFILE%\Documents\projeto-automacao
git checkout -b o07-docker-cloud
git add .github/workflows/o07-docker.yml
git add verificar_docker_O07.sh verificar_docker_O07.ps1
git commit -m "ci: O07 Docker via GitHub Actions (sem Docker local)"
git push -u origin o07-docker-cloud
```

Abra PR ou faça merge em `master`.

### Passo 2 — Disparar o job

1. https://github.com/Douglassrf/projeto-automacao/actions
2. **O07 Docker Production** → **Run workflow**
3. Aguarde ficar verde
4. Clique no job → copie o log de `=== 1) Versão do Docker ===` até `=== Concluído ===`
5. Cole em `O07_DOCKER_PRODUCTION_REPORT.md`

## Docker Build Cloud (alternativa)

https://docs.docker.com/build/cloud/ — ainda exige `docker buildx` no PC e trial 7 dias / plano pago depois. **Não é 0800 para sempre.**

## Se um dia quiser Docker local de novo

Reinstale Docker Desktop quando tiver mais RAM livre ou PC mais forte. Até lá, use GitHub Actions.
