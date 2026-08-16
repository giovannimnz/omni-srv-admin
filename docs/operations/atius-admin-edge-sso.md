# Atius Admin Edge SSO

Status: live e revalidado em 2026-07-30 para `grafana.atius.com.br`, `portainer.atius.com.br` e `docker.atius.com.br`.

Lifecycle host-local completo dos cinco sites SSO (`grafana`, `portainer`,
`docker`, `vpn`, `adguard`): `docs/operations/atius-sso-host-local-lifecycle.md`.

## Objetivo

Substituir o Apache Basic Auth como plano principal de login dos consoles administrativos pelo mesmo plano de identidade Atius já usado nos demais sites, com entrada humana em `/login`, validação server-side de `auth-token` via `GET /v1/auth/me` e segredo upstream mantido só no servidor.

## Escopo

- `grafana.atius.com.br`
- `portainer.atius.com.br`
- `docker.atius.com.br`

## Resultado final

- `/` anônimo -> `302` para `/login`
- `/login` -> tela local `Atius SSO`
- `/login` segue o modelo visual `ssh.atius.com.br/login` com logo Atius, card central, `DESTINO SEGURO`, campos e botão canônicos.
- submit com o usuário padrão Atius -> entrada real no app
- nenhuma tela de Apache Basic Auth no caminho humano final

## Arquitetura

```text
browser
  -> https://<host>.atius.com.br/login
  -> Apache SRV-1
  -> 127.0.0.1:8210 (Atius Admin Edge Gateway)
       -> GET http://127.0.0.1:8015/v1/auth/me   [valida auth-token]
       -> POST http://127.0.0.1:8015/v1/token/generate [login local Atius]
       -> upstream app
          - Grafana:  http://10.13.1.13:3005      + Basic upstream server-side
          - Portainer: https://10.12.1.12:9443    + JWT upstream server-side
          - Docker:    alias de Portainer
```

## Arquivos live

### Repo
- `modules/atius-admin-edge-sso/scripts/atius-admin-edge-gateway.js`
- `modules/atius-admin-edge-sso/configs/atius-admin-edge-gateway.json`
- `modules/atius-admin-edge-sso/scripts/start-atius-admin-edge-gateway.sh`
- `modules/atius-admin-edge-sso/configs/systemd/atius-admin-edge-gateway.service`

### Host
- `/opt/atius/atius-admin-edge-gateway.js`
- `/etc/atius/atius-admin-edge-gateway.json`
- `/usr/local/libexec/atius/start-atius-admin-edge-gateway`
- `/etc/systemd/system/atius-admin-edge-gateway.service`

### Apache vhosts
- `/etc/apache2/sites-enabled/grafana.atius.com.br.conf`
- `/etc/apache2/sites-enabled/portainer.atius.com.br.conf`
- `/etc/apache2/sites-enabled/docker.atius.com.br-le-ssl.conf`

## Serviço

- unit: `atius-admin-edge-gateway.service`
- bind local: `127.0.0.1:8210`
- health: `http://127.0.0.1:8210/_atius/healthz`

## Credenciais upstream

Somente server-side. Não expor no browser, logs, docs ou reports.

- Grafana upstream:
  - user: `admin`
  - password file: `/home/ubuntu/.secrets/grafana-admin-password`
- Portainer upstream:
  - user: `admin`
  - password file: `/home/ubuntu/.secrets/portainer-admin-password`

## Comportamento por app

### Grafana
- auth plane do usuário final: Atius SSO local `/login`
- auth upstream server-side: Basic, injetado pelo gateway
- target final validado no browser: dashboard/home do Grafana

### Portainer / Docker
- auth plane do usuário final: Atius SSO local `/login`
- auth upstream server-side: JWT Portainer (`POST /api/auth` -> `Bearer <jwt>` cacheado por ~10 min)
- `docker.atius.com.br` reutiliza o mesmo upstream do Portainer
- target final validado no browser: `#!/home`

## Validação feita

### Lifecycle final 2026-07-30

- Evidence pack pós-patch visual: `docs/evidence/atius-sso/2026-07-30-revalidation-user-report/post-ui-parity/`
- Combined report: `docs/evidence/atius-sso/2026-07-30-revalidation-user-report/post-ui-parity/combined-report.json`
- Manifesto: `docs/evidence/atius-sso/2026-07-30-revalidation-user-report/post-ui-parity/SHA256SUMS`
- Visual review: `docs/evidence/atius-sso/2026-07-30-revalidation-user-report/post-ui-parity/visual-review/login-parity-contact-sheet.png`
- Resultado: 5 sites, 10 ciclos, 40 screenshots, PASS.
- Garantia: nenhum fluxo humano ficou em `sso.atius.com.br`; todos terminaram logout em `https://<site>.atius.com.br/login`.
- Paridade visual: Grafana, Portainer e Docker passaram contra o modelo SSH SSO; VPN e AdGuard também passaram no evidence pack compartilhado.

### Browser real com o usuário padrão
- `grafana.atius.com.br/login` -> PASS -> home do Grafana
- `portainer.atius.com.br/login` -> PASS -> `#!/home`
- `docker.atius.com.br/login` -> PASS -> `#!/home`

### HTTP
- `https://grafana.atius.com.br/` -> `302 /login`
- `https://portainer.atius.com.br/` -> `302 /login`
- `https://docker.atius.com.br/` -> `302 /login`
- `https://grafana.atius.com.br/login` -> `200` tela local `Atius SSO`
- `https://portainer.atius.com.br/login` -> `200` tela local `Atius SSO`
- `https://docker.atius.com.br/login` -> `200` tela local `Atius SSO`

## Rollback

Backups criados antes da mudança:
- `/home/ubuntu/.backups/atius-sso-sites-20260730-150530/`
- `/home/ubuntu/backups/atius-sso-ui-parity-20260730-220117/`

Rollback rápido:
1. restaurar os três vhosts Apache do backup
2. `sudo apache2ctl configtest && sudo systemctl reload apache2`
3. `sudo systemctl disable --now atius-admin-edge-gateway.service`
4. opcional: restaurar `/opt/atius/atius-admin-edge-gateway.js`, `/etc/atius/atius-admin-edge-gateway.json`, `/usr/local/libexec/atius/start-atius-admin-edge-gateway`, `/etc/systemd/system/atius-admin-edge-gateway.service`

## Observações

- Este runbook substitui o Apache Basic Auth como plano principal.
- O documento antigo `docs/operations/edge-auth.md` continua útil apenas como trilha histórica / fallback / hipótese Cloudflare Access, não como estado final desejado por Giovanni.
