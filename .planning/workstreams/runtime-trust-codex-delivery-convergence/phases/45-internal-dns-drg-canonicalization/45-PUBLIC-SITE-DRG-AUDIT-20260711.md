# Public site DRG audit

Date: 2026-07-11
Status: completed with deployment backlog

## Scope

Audited every HTTPS name-based vhost loaded by Apache on `atius-srv-1`, then
checked active reverse-proxy configuration on `atius-srv-2`, `atius-srv-3`,
and `horistic-srv`. The canonical server path is OCI/DRG; `wg100` remains a
reserve path and `10.1.1.0/24` is retired.

## Readdress corrections

The following active Apache configs still targeted retired SRV-2 address
`10.1.1.2` and now target `10.12.1.12`:

- `router.zentrius.com.br-le-ssl.conf`: port `3301`.
- `mail.atius.com.br.conf`: port `8080`.
- `webmail.atius.com.br.conf`: port `8080`.
- `mailcow-le-ssl.conf`: port `8080`, including WebSocket routing.
- `dashboard-dev.atius.com.br.conf`: port `3045`.
- `backtest-dev.atius.com.br.conf`: ports `3045` and `8045`, including
  WebSocket/HMR routes.

The enabled vhosts are regular files instead of symlinks. Both the
`sites-available` copies and the files actually loaded from `sites-enabled`
were updated. Final active-config scan returned no `10.1.1.x` reference.

## Recovered sites

| Site | Result | Repair |
|---|---:|---|
| `landscape.atius.com.br/account/standalone/secrets` | 303 | SRV-3 OCI upstream from prior incident repair |
| `vault.atius.com.br` | 200 | SRV-3 OCI upstream from prior incident repair |
| `router.zentrius.com.br` | 200 | `10.1.1.2:3301` -> `10.12.1.12:3301` |
| `remote.atius-srv-1.atius.com.br` | 200 | stale noVNC port `6080` -> active `6170` |
| `mail.atius.com.br` | 200 | Mailcow unit migrated from removed Docker CLI to `podman-compose` |
| `webmail.atius.com.br` | 200 | same Mailcow recovery |
| `plane.atius.com.br` | 200 | restored Podman stack and correct `atius` network `10.89.1.0/24` |

Mailcow is enabled/active through `mailcow-podman-rootless.service`. Plane is
enabled/active through the new user unit `plane-podman.service`, with
`Linger=yes` for `ubuntu`.

## Backups

- Apache: `/var/backups/apache-drg-vhosts-20260711-175913/` on SRV-1.
- Mailcow unit: `/home/ubuntu/.backups/mailcow-podman-unit-20260711-1810/`
  on SRV-2.
- Plane compose/env:
  `/home/ubuntu/.backups/plane-podman-20260711-1817/` on SRV-1.

## Deployment backlog

The following public names still return 503 because their configured backend
has no listener or deployable runtime artifact on any canonical OCI host:

- `agent.atius.com.br`
- `aion.atius.com.br`
- `backtest-dev.atius.com.br`
- `darwin.atius.com.br`
- `dashboard-dev.atius.com.br`
- `db.atius.com.br`
- `gsd-ac.atius.com.br`
- `gsd.atius.com.br`
- `hermes.atius.com.br`
- `hermes-desktop.atius.com.br`
- `hermes-wss.atius.com.br`
- `ia.atius.com.br`
- `jenkins.atius.com.br`
- `n8n.atius.com.br`
- `orch.atius.com.br`
- `paperclip.atius.com.br`
- `pico.atius.com.br`
- `transformer.atius.com.br`

`ceo.atius.com.br` has an Apache vhost but no public DNS record. The residual
503 set is not an address-plane problem: scanning the corresponding ports on
`10.12.1.12`, `10.13.1.13`, and `10.21.1.21` found no replacement service.
Jenkins, CloudBeaver/Paperclip, Aion, and Hermes Web reference missing local
images or source/build artifacts, so no incompatible replacement image was
introduced during this network repair.

## Verification

- `apache2ctl configtest`: `Syntax OK` after each vhost change.
- `apache2`: active after reload.
- No active Apache vhost on SRV-1 references `10.1.1.x`.
- No active Apache/Nginx/Caddy/Traefik config on SRV-2, SRV-3, or Horistic
  references `10.1.1.x`.
- Mailcow local `:8080`: HTTP 200; all compose containers running.
- Plane local `:8090`: HTTP 200; all 13 compose containers running.
