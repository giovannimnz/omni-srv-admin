# Atius SSO - Manual Index

## Objetivo

Roteador canônico para entender, montar, validar, incluir e remover SSO entre
os sistemas Atius sem depender de contexto oral ou de uma fase específica.

## O que ler primeiro

### 1. Como o SSO funciona

- `docs/domain/atius-sso-learnings.md`
- `docs/domain/atius-wide-sso.md`
- `docs/domain/atius-sso-operations-manual.md`

### 2. Como montar/publicar o host SSO

- `docs/domain/atius-wide-sso.md`

Foco:

- `sso.atius.com.br` como host canônico
- ATS facade
- Keycloak como OIDC controlado
- Apache, Cloudflare, TLS, rollback, gate manual

### 3. Como incluir um app novo

- `docs/domain/atius-sso-operations-manual.md`
- `docs/domain/atius-sso-application-playbook.md`

Foco:

- allowlist de `return_to`
- middleware/proxy local
- validação server-side da sessão
- preservação de rotas públicas

### 4. Como remover um app do SSO

- `docs/domain/atius-sso-operations-manual.md`
- `docs/domain/atius-sso-application-playbook.md`

Foco:

- remoção da allowlist central
- limpeza de middleware/proxy/logout local
- rerun de testes e atualização de docs

## Modelos de trabalho

### Entender

Perguntas que este pacote responde:

- quem autentica
- quem emite o cookie compartilhado
- quem decide RBAC
- como o `return_to` é protegido
- como o logout global funciona

### Montar

Use quando o trabalho for de host/plataforma:

- publicar `sso.atius.com.br`
- preparar vhost Apache
- validar headers `X-Forwarded-*`
- inventariar Keycloak client
- confirmar rollback antes de mutação live

### Incluir

Use quando o trabalho for onboarding de app:

- `vpn.atius.com.br`
- `remote.atius.com.br`
- qualquer novo host/subdomínio Atius

### Validar

Use quando o objetivo for responder:

- o redirect está correto
- a página mostra o destino certo
- o login falha como `401`, não `500`
- o logout limpa os cookies certos

### Remover

Use quando um app deixa de participar do fluxo central de SSO.

## Artefatos de apoio

- manual operacional por tarefa:
  - `docs/domain/atius-sso-operations-manual.md`
- learnings da fundação Keycloak:
  - `.planning/phases/36-keycloak-sso-and-coexistence/36-01-SUMMARY.md`
- learnings da fachada Ats-wide:
  - `.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-LEARNINGS.md`
- pattern map:
  - `.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-PATTERNS.md`

## Skill operacional

- `~/.codex/skills/atius-sso/SKILL.md`

Uso esperado:

```text
$atius-sso
```

## Regra de segredo

Fonte de verdade:

- HashiCorp Vault

Nunca usar como autoridade:

- `.env`
- shell history
- chat
- Obsidian
- GBrain
