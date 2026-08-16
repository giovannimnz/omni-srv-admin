# Atius SSO post-UI-parity revalidation — 2026-07-30

Status: PASS.

## Escopo

| Site | Ciclos | Screenshots | Browser flow | Visual parity |
|---|---:|---:|---|---|
| `grafana.atius.com.br` | 2 | 8 | PASS | PASS |
| `portainer.atius.com.br` | 2 | 8 | PASS | PASS |
| `docker.atius.com.br` | 2 | 8 | PASS | PASS |
| `vpn.atius.com.br` | 2 | 8 | PASS | PASS |
| `adguard.atius.com.br` | 2 | 8 | PASS | PASS |

Total: 5 sites, 10 ciclos, 40 screenshots.

## Contrato validado

- Acesso anônimo entra no mesmo hostname e cai em `/login`.
- A tela `/login` mantém o hostname app-local no conteúdo e na URL.
- A tela `/login` segue o modelo visual `ssh.atius.com.br/login`:
  - fundo escuro;
  - card central;
  - logo Atius;
  - texto `Atius SSO`;
  - bloco `DESTINO SEGURO`;
  - campos `Email ou username` e `Senha`;
  - botão `Entrar com Atius SSO`.
- Login entra no app real.
- Logout limpa `auth-token` e volta para `https://<site>.atius.com.br/login`.
- `sso.atius.com.br` não aparece como hostname visível no fluxo humano dos apps.

## Arquivos principais

- `combined-report.json` — relatório agregado PASS.
- `SHA256SUMS` — manifesto SHA-256 validado.
- `visual-review/login-parity-contact-sheet.png` — comparação do modelo SSH com os cinco `/login`.
- `visual-review/<site>-contact-sheet.png` — 8 prints por site: access, login, authenticated, logged-out para dois ciclos.

## Validação executada

```text
combined-report.json -> PASS {'sites': 5, 'cycles': 10, 'screenshots': 40}
sha256sum -c SHA256SUMS -> PASS
vision login parity -> PASS nos cinco sites
vision per-site lifecycle -> PASS em 10/10 ciclos
node phase09-sso-contract.mjs -> PASS
node phase09-sso-contract.mjs --live -> PASS
node --test adguard-portal-gateway.test.mjs -> 21/21 PASS
npm run typecheck -> PASS
Next build governado via omni resource-governor -> PASS
sudo apache2ctl configtest -> Syntax OK
systemctl is-active atius-admin-edge-gateway.service adguard-portal-gateway.service vpn-frontend.service apache2.service -> active/active/active/active
journalctl desde deploy marker -> sem erros/fail/timeout
```

## Root cause deste re-run

O fluxo funcional já passava na revalidação nova, mas a paridade visual estrita falhou contra o modelo SSH. Causas:

1. `modules/atius-admin-edge-sso/scripts/atius-admin-edge-gateway.js` usava template compacto sem logo/cabeçalho canônico.
2. `home-proxy/modules/home-router-be3/scripts/adguard-portal-gateway.cjs` usava o mesmo template compacto.
3. `web/frontend/src/app/login/page.tsx` apontava para `/mono-atius-horizontal.svg`, asset inexistente; o asset real é `/atius-mark.svg`.
4. `web/frontend/tests/phase09-sso-contract.mjs` assumia `Location` absoluto e barra final no destino visual; o live correto usa `Location: /login` relativo e hostname sem barra no card.

## Patch live aplicado

- Admin-edge `/login`: template canônico com logo Atius inline, `DESTINO SEGURO`, campos e botão iguais ao modelo.
- AdGuard `/login`: mesmo template canônico.
- VPN `/login`: usa `/atius-mark.svg` real e layout canônico.
- VPN test contract: aceita `Location: /login` relativo e valida conteúdo app-local.

## Backup

Backup pré-mutação:

`/home/ubuntu/backups/atius-sso-ui-parity-20260730-220117`

Manifesto do backup validado por SHA-256.

## Observação Apache

`apache2ctl configtest` sem sudo reportou falso missing de certificado em `admin.talk.atius.com.br`, porque o usuário sem privilégios não atravessa `/etc/letsencrypt/archive`. A validação correta é:

```bash
sudo apache2ctl configtest
```

Resultado: `Syntax OK`.
