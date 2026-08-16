---
status: resolved
trigger: "User says prior PASS is false; all Atius SSO site logins broken/worse"
created: 2026-07-30T21:32:26-0300
updated: 2026-07-30T22:20:00-0300
---

## Symptoms

- User reports previous PASS is not valid.
- Required proof: five sites, two complete browser cycles each, screenshots for access/login/authenticated/logout-return, plus visual analysis.
- Hostname must remain app-local; human flow must not visibly land on `sso.atius.com.br`.

## Active hypothesis

The HTTP redirect shell may look correct while real browser credential/logout lifecycle fails, or the previous harness may have validated insufficient UI states. Treat all prior PASS as suspect until fresh evidence is produced.

## Evidence log

- 2026-07-30T21:32:26-0300 — debug reopened after user rejected previous result.
- 2026-07-30T21:44:00-0300 — fresh browser baseline ran per-site with 5 sites, 10 cycles, 40 screenshots: functional PASS.
- 2026-07-30T21:55:00-0300 — visual review against `/home/ubuntu/GitHub/Prints/sso-ssh-base-model.png` found strict UI parity failure: admin-edge and AdGuard used compact no-logo template; VPN referenced missing `/mono-atius-horizontal.svg` instead of real `/atius-mark.svg`.
- 2026-07-30T22:01:17-0300 — backup verified: `/home/ubuntu/backups/atius-sso-ui-parity-20260730-220117`.
- 2026-07-30T22:08:22-0300 — live patch deployed to `/opt/atius/atius-admin-edge-gateway.js`, `/opt/atius/adguard-portal-gateway.js`, and rebuilt/restarted `vpn-frontend.service`.
- 2026-07-30T22:14:00-0300 — post-patch E2E passed: `docs/evidence/atius-sso/2026-07-30-revalidation-user-report/post-ui-parity/combined-report.json` -> `PASS {'sites': 5, 'cycles': 10, 'screenshots': 40}`.
- 2026-07-30T22:15:00-0300 — visual model review passed for Grafana, Portainer, Docker, VPN, and AdGuard. Each `/login` now shows the Atius logo, `Atius SSO`, `DESTINO SEGURO`, host-local destination, fields, and button matching the SSH model.
- 2026-07-30T22:16:00-0300 — technical gates passed: `phase09-sso-contract.mjs`, `phase09-sso-contract.mjs --live`, `adguard-portal-gateway.test.mjs` 21/21, `npm run typecheck`, governed Next build, `sudo apache2ctl configtest`, service states active, and logs clean since deploy marker.

## Root cause

1. The previous PASS was rejected because it did not include strict visual parity with the SSH SSO model.
2. Admin-edge and AdGuard local `/login` pages were functionally correct but still used an old compact template without the canonical Atius mark and spacing.
3. VPN `/login` referenced `/mono-atius-horizontal.svg`, which does not exist in the deployed frontend; the real asset is `/atius-mark.svg`.
4. The VPN live contract test assumed an absolute `Location` header even though the production proxy correctly returns `Location: /login` relative to `vpn.atius.com.br`.

## Final verdict

Resolved. All five sites pass two consecutive browser cycles and visual parity review:

- `grafana.atius.com.br/login`
- `portainer.atius.com.br/login`
- `docker.atius.com.br/login`
- `vpn.atius.com.br/login`
- `adguard.atius.com.br/login`

The visible hostname never changes to `sso.atius.com.br` in the human app flow.
