# Atius SSO - Learnings Consolidados

## Objetivo

Consolidar as decisões, lições, padrões e surpresas que saíram das fases 36 e
42 para que futuras integrações de SSO reutilizem o que já foi aprendido.

## Decisões

### `sso.atius.com.br` é a UX canônica de login

O login visual do usuário final deve acontecer em `sso.atius.com.br`, não na
tela crua do Keycloak.

**Por quê:** a fachada ATS precisa controlar `return_to`, callback, reemissão
do `auth-token` e logout global sem quebrar compatibilidade.
**Fonte:** `42-02-SUMMARY.md`, `42-LEARNINGS.md`

### Keycloak fica como IdP/OIDC; ATS continua dono da sessão local

O Keycloak identifica; o ATS continua emitindo o `auth-token` e mantendo a
compatibilidade de sessão.

**Por quê:** a migração exigia preservar o contrato legado antes de provar uma
autorização OIDC nativa.
**Fonte:** `36-01-SUMMARY.md`, `42-02-SUMMARY.md`

### RBAC continua no banco ATS e em `permissions.js`

Claims do IdP não viram a fonte de autorização por padrão.

**Por quê:** isso preserva o comportamento atual das rotas protegidas e evita
transformar o Keycloak em backend acidental de permissão.
**Fonte:** `42-01-SUMMARY.md`, `42-LEARNINGS.md`

### Publicação live de edge é um gate separado do código

Código pronto não significa edge pronto.

**Por quê:** DNS, Cloudflare, Apache reload, headers, client Keycloak e rollback
precisam de checkpoint manual.
**Fonte:** `42-03-PLAN.md`, `.planning/STATE.md`

## Lições

### Redirect seguro precisa de teste executável

Descrever allowlist em prosa não basta; foi necessário um contrato testável
para `return_to`.

**Contexto:** o redirect é a fronteira de segurança de todo o fluxo SSO.
**Fonte:** `42-01-SUMMARY.md`, `42-LEARNINGS.md`

### CORS errado parece bug de senha

Se `atius-api` não aceitar `Origin: https://sso.atius.com.br`, o login quebra
como `500` antes mesmo de validar a credencial.

**Contexto:** isso apareceu na fase 42 ao ligar o shell SSO ao backend ATS.
**Fonte:** `docs/domain/atius-wide-sso.md`, `60-LOGS/2026-06-28-phase42-atius-wide-sso.md`

### Header drift em proxy quebra SSO silenciosamente

`X-Forwarded-Host`, `X-Forwarded-Proto` e `X-Forwarded-Port` não podem ficar
implícitos nem herdados “por sorte”.

**Contexto:** o middleware do ATS depende disso para decidir host e redirect.
**Fonte:** `42-03-PLAN.md`, `.planning/codebase/CONCERNS.md`

### Logout browser-based é requisito, não detalhe

Fluxos de logout só com teste de backend não capturam limpeza de cookie, loop
de auto-login e handoff para end-session.

**Contexto:** o contrato de logout precisou de cobertura própria em browser.
**Fonte:** `42-01-SUMMARY.md`, `42-02-SUMMARY.md`

## Padrões

### Padrão de fachada SSO

Separar o host de login do IdP bruto e colocar a fachada no frontend ATS.

**Quando usar:** sempre que a Atius precisar preservar `auth-token`, RBAC
local, allowlist de redirect e logout global compatível.
**Fonte:** `42-02-SUMMARY.md`, `42-PATTERNS.md`

### Padrão de bridge OIDC para cookie legado

Next valida estado do browser; Fastify troca o `code`; só `auth-token` volta ao
browser.

**Quando usar:** migrações de SSO em que o sistema legado ainda não pode expor
um modelo OIDC-native de sessão.
**Fonte:** `42-02-SUMMARY.md`, `42-PATTERNS.md`

### Padrão fail-closed para smoke live

Smokes de auth devem exigir env explícita e falhar fechado sem fallback de
credencial embutida.

**Quando usar:** toda validação live que encoste em credenciais, cookies,
client secret ou login real.
**Fonte:** `42-01-SUMMARY.md`, `42-LEARNINGS.md`

### Padrão de evidência sem segredo

Registrar timestamp, host, caminho, status e backup, mas nunca valores.

**Quando usar:** qualquer rollout envolvendo token, cookie, senha, JWT secret,
OIDC secret ou credencial de smoke.
**Fonte:** `42-03-PLAN.md`, `42-VALIDATION.md`

## Surpresas

### A Wave 0 virou arquitetura, não só preparação

O que parecia “fase de teste” acabou definindo os contratos centrais de
redirect, logout, secret hygiene e bridge.

**Impacto:** reduziu o risco da implementação e deixou a publicação mais
determinística.
**Fonte:** `42-01-SUMMARY.md`, `42-LEARNINGS.md`

### Keycloak pronto não migra app sozinho

A fase 36 provou OIDC e federação LDAP, mas não migrava nenhum app por si só.

**Impacto:** foi necessário criar a fase 42 como fachada/control plane de SSO,
e não tentar “apontar tudo para Keycloak”.
**Fonte:** `36-01-SUMMARY.md`, `42-CONTEXT.md`

### O manual virou parte da arquitetura

Os runbooks canônicos de SSO passaram a carregar contrato técnico, não só
documentação descritiva.

**Impacto:** mudanças futuras de SSO devem tratar os manuais como source of
truth arquitetural junto com código e testes.
**Fonte:** `42-LEARNINGS.md`, `docs/domain/atius-wide-sso.md`
