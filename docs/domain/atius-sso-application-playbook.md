# Atius SSO - Application Playbook

## Objetivo

Manual canônico para entender, montar, incluir, validar, operar e remover SSO Atius entre os nossos sistemas.

Leitura de apoio:

- `docs/domain/atius-sso-manual-index.md`
- `docs/domain/atius-sso-learnings.md`

Este documento não substitui `docs/domain/atius-wide-sso.md`.

Divisão de responsabilidade:

- `docs/domain/atius-wide-sso.md`
  - contrato de edge/publicação do host `sso.atius.com.br`
  - Apache, Cloudflare, TLS, Keycloak client, gate manual, rollback
- `docs/domain/atius-sso-application-playbook.md`
  - contrato de aplicação
  - como um app entra, usa, valida e sai do SSO

## Modelo mental

### Hostes canônicos

- login humano canônico: `https://<app>.atius.com.br/sso`
- alias de compatibilidade: `https://<app>.atius.com.br/login` -> `/sso` com `308`
- control plane/fallback: `https://sso.atius.com.br/login`
- logout global: `https://sso.atius.com.br/api/sso/logout`
- IdP OIDC/fallback: `https://auth.atius.com.br/realms/atius`
- backend ATS de validação de sessão: `https://api.atius.com.br/v1/auth/me`

### Mapa entre sistemas

```text
browser
  -> app.atius.com.br
  -> redirect para app.atius.com.br/sso?return_to=<app-url>
  -> facade local exige return_to same-origin e autentica via ATS
  -> auth-token volta para .atius.com.br
  -> app valida sessao em api.atius.com.br/v1/auth/me
  -> proxy server-side do app injeta credencial interna no backend privado
```

Leitura prática:

- `sso.atius.com.br` é o control plane/fallback central e owner do logout global
- `/sso` no app é a facade humana canônica do shell de login
- `auth.atius.com.br` é o IdP/OIDC quando o fluxo usa Keycloak
- `api.atius.com.br` é a autoridade reaproveitável para validar a sessão ATS
- o app integrado nunca deve expor o segredo do backend interno no browser

### Sessão compartilhada

- cookie compartilhado: `auth-token`
- domínio em produção: `.atius.com.br`
- o SSO central controla login/logout e emissão do cookie
- os apps consomem a sessão; não devem reinventar autenticação paralela

### Papel de cada lado

#### `sso.atius.com.br`

- recebe o usuário
- valida `return_to`
- mostra o destino seguro
- faz login ATS e/ou bridge OIDC
- emite ou limpa `auth-token`

#### App integrado

- detecta ausência/invalidade da sessão
- redireciona para `<app>.atius.com.br/sso?return_to=<url-atual>`
- aceita `return_to` somente do próprio origin
- valida a sessão com `GET /v1/auth/me` ou via endpoint local equivalente
- expõe só proxy server-side para backend interno sensível

## Tipos de integração

### 1. App web protegido por SSO com backend próprio

Exemplo: `vpn.atius.com.br`

Padrão:

- middleware/proxy local redireciona para a facade `/sso` do próprio host
- `/login` é alias `308`, nunca uma segunda implementação de login
- endpoint local de sessão confirma `auth-token`
- browser nunca recebe token interno do backend
- logout local limpa cookies e volta ao fluxo canônico

### 2. App/proxy de recurso interno protegido por cookie ATS

Exemplo: `remote.atius.com.br/mt5/*`

Padrão:

- gate local verifica `auth-token`
- autorização continua local ao sistema (`can_access_trade`, `is_admin`, etc.)
- `return_to` volta para o recurso original

### 3. Host ATS nativo

Exemplos:

- `trade.atius.com.br`
- `painel.atius.com.br`
- `dashboard.atius.com.br`
- `backtest.atius.com.br`
- `strategy.atius.com.br`
- `admin.atius.com.br`

Padrão:

- estão na allowlist do shell central
- o próprio ATS controla a navegação protegida e o bridge SSO

## Como montar um app novo no SSO Atius

Use esta sequência quando o app ainda não tem integração nenhuma com o SSO:

1. Decidir o papel do app:
   - host ATS nativo
   - app com backend próprio
   - proxy de recurso interno
2. Definir host público, paths protegidos e paths públicos.
3. Confirmar qual backend interno o proxy local vai falar e qual credencial interna ele vai injetar.
4. Adicionar o host/path na allowlist central do ATS.
5. Implementar o gate local:
   - facade `/sso` com proxy mínimo de shell/assets/endpoints ATS
   - alias `/login` com `308`
   - forwarded host/proto exatos, CORS do app e `return_to` same-origin
   - middleware de redirect
   - endpoint local de sessão
   - proxy server-side autenticado
   - logout local
6. Validar redirect, cookie, sessão, CORS e fake login.
7. Documentar no repo do app, no `omni-srv-admin`, no Obsidian e no GBrain.

### Pré-requisitos mínimos

- host público definitivo
- dono do backend interno
- nome da credencial interna
- estratégia de rotas públicas
- critério de autorização local, quando existir

Sem esses itens, a integração tende a abrir exceções implícitas e regressões de segurança.

## Contrato mínimo para incluir um app novo

### Passo 1. Definir o destino final

Antes de tocar no código:

- hostname público exato
- paths que podem ser `return_to`
- quais páginas precisam de login
- quais rotas devem continuar públicas

Exemplos:

- aceitável: `https://vpn.atius.com.br/diagnostics`
- não aceitável: `https://vpn.atius.com.br/api/auth/session`
- não aceitável: `https://vpn.atius.com.br/install/...` se o contrato exigir link público

### Passo 2. Atualizar a allowlist central

Arquivo central:

- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts`

Adicionar:

- host em `ALLOWED_SSO_RETURN_HOSTS`
- prefixes permitidos em `ALLOWED_SSO_RETURN_PATHS`

Regras:

- apenas `https`
- sem wildcard
- sem userinfo
- sem path traversal
- sem host confusion

As-built Casa Remote Gateway, validado em 2026-07-20:

| Host | Paths aceitos |
|---|---|
| `ssh.atius.com.br` | `/ssh-giovanni-w11-pc`, `/ssh-giovanni-wsl-pc`, `/ssh-giovanni-s23`, `/ssh-horistic-srv` |
| `rdp.atius.com.br` | `/giovanni-w11-pc` |

Adicionar um DNS/vhost novo sem atualizar essa tabela no código faz o ATS
apagar `atius_sso_login_return_to` e renderizar o fallback
`trade.atius.com.br/`. Portanto, o smoke de inclusão precisa provar também o
texto visual de “Destino seguro” em browser anônimo, além do primeiro `302`.

### Passo 3. Integrar o app

Padrão mínimo:

1. middleware/proxy detecta falta de `auth-token`
2. redirect para `sso.atius.com.br/login?return_to=<url-atual>`
3. endpoint local valida sessão
4. proxy server-side injeta token interno do backend
5. logout local volta ao fluxo canônico

Quando houver backend interno sensível:

- o browser fala apenas com o proxy local do app
- o proxy local consulta `/v1/auth/me`
- o proxy local injeta a credencial interna
- o backend interno não deve confiar no browser diretamente

### Passo 4. Preservar rotas públicas explicitamente

Não misturar “página protegida” com “endpoint público por conveniência”.

Liste as exceções.

Exemplo `vpn-atius`:

- `/install/*` continua público

### Passo 5. Validar

#### Contrato central

```bash
cd /home/ubuntu/GitHub/Atius-Capital/ats
npx jest --config jest.backend.config.js tests/backend/auth/test_sso_redirect_allowlist.test.js --runInBand
```

#### Chain HTTP

```bash
curl -Iks "https://<app>.atius.com.br/"
curl -Iks "https://sso.atius.com.br/login?return_to=https%3A%2F%2F<app>.atius.com.br%2F"
curl -Iks "https://sso.atius.com.br/api/sso/login?return_to=https%3A%2F%2F<app>.atius.com.br%2F"
```

#### Tela

Validar que a página mostra o destino real, não um default errado.

Exemplo esperado:

- `Destino seguro: vpn.atius.com.br/`

#### Sessão

Com credencial falsa, o host SSO deve responder corretamente sem `500`:

```bash
curl -isS -X POST 'https://sso.atius.com.br/v1/token/generate' \
  -H 'Origin: https://sso.atius.com.br' \
  -H 'Content-Type: application/json' \
  --data '{"email":"fake@example.com","senha":"senha-falsa"}'
```

Esperado:

- `401 Credenciais inválidas.`

### Passo 6. Documentar

Atualizar:

- repo do app
- `omni-srv-admin` quando a mudança afeta contrato geral
- Obsidian
- GBrain

## Contrato mínimo para remover um app do SSO

### Remoção lógica

1. remover host/prefixos de `redirects.ts`
2. remover ou adaptar middleware local do app
3. remover endpoint local de sessão/logout se não forem mais necessários
4. remover docs específicas do app
5. rerodar testes de redirect allowlist

### Remoção operacional

Checar se o app ainda depende de:

- `auth-token`
- `/v1/auth/me`
- `sso.atius.com.br/login`
- `sso.atius.com.br/api/sso/logout`
- proxy interno autenticado

Se sim, a remoção ainda não está completa.

## O que não fazer

- não embutir token interno no browser
- não tratar Keycloak como página visual canônica do usuário final
- não usar fallback implícito para `trade.atius.com.br`
- não aceitar `return_to` arbitrário
- não documentar secrets
- não salvar cookie/token/password em logs, docs, planning, Obsidian ou GBrain
- não misturar rotas públicas e privadas sem lista explícita
- não criar um segundo login local “temporário” sem documentar explicitamente por que ele existe e como será removido

## Checklist de inclusão

1. Host e paths finais definidos
2. Allowlist central atualizada
3. Middleware/proxy local implementado
4. Sessão validada server-side
5. Token interno removido do browser
6. Rotas públicas preservadas explicitamente
7. Teste de redirect allowlist passou
8. HTML da tela mostra o destino real
9. Login fake retorna `401`, não `500`
10. Repo + Obsidian + GBrain atualizados

## Checklist de remoção

1. Host removido da allowlist central
2. Redirect do app removido/ajustado
3. Sessão local removida/ajustada
4. Dependência em `auth-token` revisada
5. Testes rerodados
6. Docs e worklogs atualizados

## Referências de código

### Central ATS

- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/sso/login/page.tsx`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/login/route.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/logout/route.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts`
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_redirect_allowlist.test.js`

### Runbooks

- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-wide-sso.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-application-playbook.md`

### Exemplo de app integrado

- `/home/ubuntu/GitHub/vpn-atius/docs/SSO-ATIUS.md`
- `/home/ubuntu/GitHub/vpn-atius/web/frontend/src/lib/atius-sso.ts`

## Segredos

Fonte de verdade:

- HashiCorp Vault

Nunca usar como fonte autoritativa:

- `.env`
- `.zshrc`
- shell history
- chat
- Obsidian
- GBrain

## Skill operacional

Skill canônico:

- `~/.codex/skills/atius-sso/SKILL.md`

Uso esperado:

```text
$atius-sso
```
