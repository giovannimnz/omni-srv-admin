# Atius SSO - Source of Truth

> **Status Normativo**: **ABSOLUTO E MANDATÓRIO (Modelo PM2 Consagrado)**  
> **Referência Operacional Padrão-Ouro**: `https://pm2.atius.io/login` e `https://pm2.atius.com.br/login`

## Contract capsule

- **Human route**: Canonical app-local `https://<app>.<dominio>/login`, mantido visível no mesmo host (`same-host`).
- **Proibição Estrita de Redirecionamento Externo**: É terminantemente proibido redirecionar o navegador do usuário para `https://sso.atius.com.br/login` ou `https://sso.atius.io/login` durante fluxos de login em aplicações.
- **Shell Canônico Unificado (Padrão PM2)**:
  - Card central escuro `448px` (`border-radius: 12px`, fundo `#171b22`, borda sutil).
  - Logotipo oficial Atius Mark SVG com texto discreto "Atius SSO".
  - **DESTINO SEGURO**: Exibe exclusivamente o `URL.hostname` puro da aplicação acessada (ex: `pm2.atius.io`, `gitlab.atius.io`, `painel.atius.com.br`), acompanhado do ícone de escudo (`shield`) laranja `#f97316` / `#ff7112`.
  - Inputs com altura `44px`: campo de login com ícone 👤, campo de senha com ícone 🔒 e botão de olho 👁 de toggle nativo.
  - Botão de ação primário em laranja institucional (`#f97316` / `#ff7112`) com texto `"Entrar com Atius SSO"`.
  - **Zero barras azuis**: Proibido qualquer artefato visual destoante (como a linha azul PatternFly do Keycloak).
- **Zero Query Leak**: Rota limpa `/login` sem parâmetros expostos na URL (`?return_to=...`, `?client_id=...`). Destino mantido via cookie host-only seguro `atius_sso_login_return_to`.
- **Destination lifecycle**: `valid | missing | rejected` across entry, login, logout-complete, re-entry, and return.
- **Central logout**: POST-only `/api/sso/logout` with real browser `Origin`, `Content-Type: application/json`, and session-bound one-time `X-CSRF-Token`; GET, wrong Origin, wrong content type, missing/invalid/replayed CSRF fail closed.
- **Rollback**: backup, restore, contract rerun, and readback are mandatory.

## Canonical owner manuals

- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-fleet-login-and-sso-governance.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-wide-sso.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-operations-manual.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-application-playbook.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-lifecycle-matrix.md`

## Canonical knowledge and readback

- Obsidian Vault:
  - `Operations/Autenticacao-e-SSO/00-INDEX-Autenticacao-e-SSO.md`
  - `Operations/Autenticacao-e-SSO/Diretriz-Canonica-Telas-de-Login-e-SSO.md`
  - `Operations/Autenticacao-e-SSO/Matriz-Sistemas-Login-Frota-Atius.md`
- GBrain full slug:
  `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico`

## Secrets rule

HashiCorp Vault is authoritative. Record identifiers only:
- profile `browser-login`
- path `kv/atius/browser-login/access-keys`
- fields `username`, `password`, `totp_secret`
