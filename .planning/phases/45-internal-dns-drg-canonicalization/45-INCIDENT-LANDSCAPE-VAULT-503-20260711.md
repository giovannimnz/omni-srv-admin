# Incident: Landscape and Vaultwarden 503 after legacy VPN retirement

Date: 2026-07-11
Status: resolved

## Impact

- `https://landscape.atius.com.br/account/standalone/secrets` returned Apache 503.
- `https://vault.atius.com.br/` returned Apache 503.

## Root cause

The Apache edge on `atius-srv-1` still proxied both services to the retired
`atius-srv-3` VPN address `10.1.1.3`. The applications were healthy, but the
edge could no longer reach their configured upstreams.

## Live repair

- Landscape upstream: `https://10.13.1.13:443/`.
- Landscape `/ping` upstream: `http://10.13.1.13:80/ping`.
- Vaultwarden HTTP and WebSocket upstream: `10.13.1.13:8088`.
- Apache `configtest` passed and `apache2` was reloaded successfully.
- LXD compatibility listeners were readdressed from `10.1.1.3:9088/9443` to
  `10.13.1.13:9088/9443`; the active Apache route uses the standard 80/443
  listeners.

## Backups

- `atius-srv-1`: vhost copies with suffix `.bak.20260711-172823` beside the
  active files in `/etc/apache2/sites-available/`.
- `atius-srv-3`:
  `/home/ubuntu/.backups/landscape-oci-proxy-20260711-172823/`.

## Validation

- Landscape origin: HTTP 303 to the classic login with the requested
  `next_url` preserved.
- Landscape public endpoint: HTTP 303 through Cloudflare.
- Vaultwarden origin: HTTP 200.
- Vaultwarden public endpoint: HTTP 200.
- Landscape HTTP `/ping` origin path: HTTP 200.

Historical Phase 29 artifacts retain `10.1.1.3` as execution evidence. They
must not be reused as current deployment configuration.
