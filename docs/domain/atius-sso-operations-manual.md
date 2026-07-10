# Atius SSO - Operations Manual

## Objetivo

Manual operacional para entender, montar, incluir, validar e remover SSO entre
os sistemas Atius. Use este documento quando a tarefa for prática e precisar de
sequência executável, não apenas contexto arquitetural.

Fontes canônicas complementares:

- `docs/domain/atius-sso-manual-index.md`
- `docs/domain/atius-wide-sso.md`
- `docs/domain/atius-sso-application-playbook.md`
- `.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-LEARNINGS.md`
- `~/.codex/skills/atius-sso/SKILL.md`

## Contrato curto

- Login canônico: `https://sso.atius.com.br/login`
- Logout global: `https://sso.atius.com.br/api/sso/logout`
- IdP/OIDC: `https://auth.atius.com.br/realms/atius`
- Validação de sessão: `GET https://api.atius.com.br/v1/auth/me`
- Cookie compartilhado: `auth-token`
- Fonte de segredo: HashiCorp Vault

O app integrado deve validar a sessão server-side e nunca expor credencial
interna do backend no browser.

## Como funciona

```text
browser
  -> app.atius.com.br/path
  -> app detecta falta de auth-token
  -> redirect para sso.atius.com.br/login?return_to=<app-url>
  -> sso valida return_to e autentica
  -> auth-token emitido para .atius.com.br
  -> app consulta api.atius.com.br/v1/auth/me
  -> app libera página/proxy server-side
```

Papéis:

- `sso.atius.com.br`: login/logout, `return_to`, shell visual e emissão/limpeza
  da sessão ATS.
- `auth.atius.com.br`: IdP/OIDC/Keycloak quando o fluxo usar bridge OIDC.
- `api.atius.com.br`: autoridade de sessão ATS reaproveitável.
- App de destino: gate local, autorização local quando existir, proxy interno e
  exceções públicas.

## Montar SSO do zero em um app

Use quando o app ainda não tem integração com SSO Atius.

1. Definir o host público exato.
2. Classificar o app:
   - host ATS nativo;
   - app com backend próprio;
   - proxy para recurso interno.
3. Listar paths protegidos e paths públicos.
4. Definir backend interno e nome da credencial server-side.
5. Adicionar host/path na allowlist central:
   `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts`
6. Implementar no app:
   - middleware/gate de redirect;
   - endpoint local de sessão;
   - proxy server-side para backend interno;
   - logout local.
7. Validar:
   - teste de allowlist;
   - chain HTTP;
   - login fake retorna `401`, não `500`;
   - browser não recebe token interno;
   - logout limpa cookie host-only e `.atius.com.br`.
8. Documentar no repo do app, `omni-srv-admin`, Obsidian e GBrain.

## Incluir app novo em SSO já existente

Use quando o SSO central já existe e o app só precisa entrar no fluxo.

Checklist:

1. Confirmar host e paths finais.
2. Confirmar se existe rota pública que precisa continuar anônima.
3. Atualizar a allowlist central em `redirects.ts`.
4. Implementar ou adaptar middleware/proxy local.
5. Validar sessão com `GET /v1/auth/me`.
6. Garantir que secrets internos ficam só no servidor.
7. Rodar testes e smokes.
8. Atualizar docs e memória operacional.

Teste central:

```bash
cd /home/ubuntu/GitHub/Atius-Capital/ats
npx jest --config jest.backend.config.js tests/backend/auth/test_sso_redirect_allowlist.test.js --runInBand
```

Smokes mínimos:

```bash
curl -Iks "https://<app>.atius.com.br/"
curl -Iks "https://sso.atius.com.br/login?return_to=https%3A%2F%2F<app>.atius.com.br%2F"
curl -Iks "https://sso.atius.com.br/api/sso/login?return_to=https%3A%2F%2F<app>.atius.com.br%2F"
```

Login fake:

```bash
curl -isS -X POST 'https://sso.atius.com.br/v1/token/generate' \
  -H 'Origin: https://sso.atius.com.br' \
  -H 'Content-Type: application/json' \
  --data '{"email":"fake@example.com","senha":"senha-falsa"}'
```

Esperado: `401 Credenciais inválidas.`

## Validar integração existente

Validação mínima:

1. `curl -Iks` na raiz do app sem cookie.
2. `curl -Iks` no login SSO com `return_to`.
3. `curl -Iks` em `/api/sso/login`.
4. Teste de allowlist se o host depende do ATS central.
5. Browser/DevTools para confirmar destino visual real.
6. Logout global para confirmar limpeza de cookies.

Critérios de aceite:

- sem fallback indevido para `trade.atius.com.br`;
- sem open redirect;
- sem token interno no bundle ou network do browser;
- `auth-token` validado server-side;
- logout não entra em loop de auto-login;
- evidência sem segredo.

## Remover app do SSO

Use quando um app deixa de participar do fluxo central.

1. Remover host/path de `redirects.ts`.
2. Remover ou adaptar middleware local de redirect.
3. Remover endpoint local de sessão/logout se não houver mais dependência.
4. Remover proxy server-side somente se o app não depender dele para proteger
   backend interno.
5. Rerodar teste de allowlist.
6. Rodar smokes para garantir que o app não chama mais `sso.atius.com.br` por
   engano.
7. Atualizar docs no repo do app, `omni-srv-admin`, Obsidian e GBrain.

Não considere removido se o app ainda depende de:

- `auth-token`;
- `/v1/auth/me`;
- `sso.atius.com.br/login`;
- `sso.atius.com.br/api/sso/logout`;
- proxy interno autenticado com sessão ATS.

## Publicar ou alterar o host SSO

Quando a mudança for no host `sso.atius.com.br`, não use apenas este manual.
Siga `docs/domain/atius-wide-sso.md`.

Antes de mutação live:

```bash
bash scripts/sso-edge-smoke.sh --dry-run --assert-status --assert-headers
bash scripts/keycloak-sso-client-check.sh inventory --realm atius --client-id sso.atius.com.br
bash scripts/sso-secret-hygiene-scan.sh
```

O gate live precisa confirmar:

- before-state Cloudflare/DNS/TLS;
- backup Apache;
- client Keycloak sem imprimir secret;
- rollback testado;
- env live de smoke carregada pelo operador.

## Evidência permitida

Pode registrar:

- timestamp;
- host;
- comando;
- status;
- caminho de backup;
- nome da variável de ambiente;
- path do Vault.

Não registrar:

- valor de cookie;
- senha;
- token;
- client secret;
- JWT;
- screenshot com segredo;
- shell history com credencial.

## Template de registro de mudança

```markdown
## SSO change - <app>

- Data:
- App/host:
- Tipo: mount | include | validate | remove
- Paths protegidos:
- Paths públicos:
- Allowlist alterada: sim/nao
- Proxy server-side: sim/nao
- Backend interno:
- Credencial interna: <nome da variavel ou path Vault, sem valor>
- Testes:
- Smokes:
- Rollback:
- Docs atualizados:
```
