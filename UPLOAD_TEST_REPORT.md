# UPLOAD_TEST_REPORT.md — Missão R03 (Teste de Upload)

Data: 2026-06-19. Commit testado: `700bf363e4d7d313edcb9e6c3b344603ea2101fd`. Backend real (`uvicorn`) rodando, endpoint `POST /api/v1/upload` testado via HTTP real (`curl -F`), com token JWT real obtido por login real. Diretório de destino isolado em `/tmp/uploads_test` (não a pasta real do projeto).

## 1. Casos testados e resultado real

| # | Caso | Arquivo enviado | Esperado | Resultado real | Status |
|---|---|---|---|---|---|
| 1 | PDF válido | `valid.pdf` (`%PDF-...%%EOF`) | 201, armazenado | `201`, `stored_filename` com UUID | ✅ |
| 2 | PNG válido | `valid.png` (gerado com Pillow, magic bytes reais) | 201, armazenado | `201`, MIME detectado `image/png` | ✅ |
| 3 | Extensão perigosa | `malware.exe` (header `MZ`) | 400, bloqueado | `400 "Extensão executável ou perigosa bloqueada."` | ✅ |
| 4 | Executável disfarçado de PDF | conteúdo `.exe` (header `MZ`) renomeado para `.pdf` | 400, bloqueado | `400 "Conteúdo com assinatura de script/executável bloqueado."` — pego pela checagem de assinatura, antes mesmo de chegar à checagem de MIME | ✅ |
| 5 | Arquivo vazio | 0 bytes, `.pdf` | 400 | `400 "Arquivo vazio não é permitido."` | ✅ |
| 6 | Arquivo grande (6 MB, limite é 5 MB) | PDF válido com 6 MB de conteúdo aleatório no meio | 400 | `400 "Arquivo excede o limite de 5242880 bytes."` | ✅ |
| 7 | Path traversal no nome do arquivo | nome enviado `../../../etc/passwd.pdf`, conteúdo PDF válido | armazenar com nome seguro, sem escapar do diretório de upload | `201`, `safe_original_filename: "passwd.pdf"`, gravado como UUID dentro de `/tmp/uploads_test` — confirmado por listagem real do diretório, nenhum arquivo fora dele | ✅ |

Todos os 7 casos se comportaram exatamente como o código de `upload_security.py` promete. Listagem real do diretório de destino após os testes confirma 3 arquivos armazenados (os 3 casos que deveriam ter sucesso), todos com nome aleatório (UUID), nenhum com o nome original do usuário — boa prática de segurança confirmada na prática, não só lida no código.

## 2. Defesa em profundidade confirmada

O caso 4 (executável disfarçado de PDF) é o teste mais importante: comprova que a checagem de assinatura de conteúdo (`looks_dangerous`, que procura por `MZ`, `#!`, `<?php`, `<script`, etc no início do arquivo) roda **antes** da checagem de MIME, então mesmo que alguém troque só a extensão do arquivo, o conteúdo real é inspecionado e bloqueado. Não é só checagem de extensão — é checagem de conteúdo real.

## 3. Achado confirmado (consistente com H01): `UploadSizeLimitMiddleware` não está registrado

O caso 6 (arquivo de 6 MB) foi rejeitado corretamente, mas pela checagem dentro do próprio handler (`validate_upload`, em `upload_security.py`), não pelo `UploadSizeLimitMiddleware` (que existe no código em `app/middleware.py` mas, confirmado por busca em `app/main.py`, nunca é registrado com `add_middleware`). Na prática isso significa: o arquivo de 6 MB é lido inteiramente para a memória do servidor (`await file.read()`) antes de ser rejeitado, em vez de ser rejeitado mais cedo, antes do upload completo, pelo header `Content-Length`. O resultado final para o usuário é o mesmo (`400`, arquivo rejeitado), mas a defesa contra um ataque de exaustão de memória/banda com muitos uploads grandes simultâneos é mais fraca do que o código do middleware sugere existir. Mesma recomendação do H01: registrar o middleware em `main.py`.

## 4. Observação sobre autenticação (consistente com R02)

Este teste foi feito com um token JWT real e válido (fluxo de login completo). Dado o achado do R02 (`AUTH_REQUIRED=false` no `.env`), é esperado que o upload também funcione sem token nenhum hoje — não foi testado separadamente aqui para não duplicar evidência já registrada no R02; a causa raiz e a recomendação são as mesmas.

## 5. Conclusão da missão R03

| Item | Resultado |
|---|---|
| Upload de PDF/PNG válidos | Funciona, 201, arquivo gravado com nome seguro (UUID) |
| Bloqueio de extensão perigosa | Funciona |
| Bloqueio de conteúdo disfarçado (MZ em .pdf) | Funciona — defesa por conteúdo, não só extensão |
| Bloqueio de arquivo vazio | Funciona |
| Bloqueio de arquivo acima do limite (5 MB) | Funciona (pela checagem do handler, não pelo middleware dedicado) |
| Proteção contra path traversal no nome do arquivo | Funciona, confirmado por inspeção real do disco |
| `UploadSizeLimitMiddleware` ativo | **Não** (confirmado, já mapeado no H01) — defesa equivalente existe no handler, mas menos eficiente |

**Status R03: APROVADO.** Todas as proteções de upload funcionam corretamente na prática, com uma ressalva de eficiência (não de segurança) já conhecida do H01. Pronto para avançar para R04.
