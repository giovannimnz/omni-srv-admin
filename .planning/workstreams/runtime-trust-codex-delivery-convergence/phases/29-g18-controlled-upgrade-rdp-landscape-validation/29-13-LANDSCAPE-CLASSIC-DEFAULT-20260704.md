---
phase: 29
date: 2026-07-04
status: applied
scope: landscape-classic-default-ui
---

# Landscape Classic UI Default

## Requirement

The default Landscape login flow should land in the classic UI, because the
Vault/secrets administration screens live there and are not available in the
modern `/new_dashboard/` UI.

## Changes Applied

On `atius-srv-1`, the HTTPS vhost at
`/etc/apache2/sites-available/landscape.atius.com.br.conf` was changed from:

```apache
RewriteRule ^/?$ /new_dashboard/ [R=302,L,NE]
```

to:

```apache
RewriteCond %{QUERY_STRING} ^$
RewriteRule ^/?$ /account/standalone/secrets [R=302,L,NE]
```

The query-string condition is required because the classic unauthenticated flow
redirects to:

```text
/?next_url=%2Faccount%2Fstandalone%2Fsecrets
```

That callback must be proxied to Landscape so the login page can render. If
Apache redirects it again, the login flow loops.

Backups on `atius-srv-1`:

- `/home/ubuntu/.backups/apache-landscape-classic-default-20260704T223757Z`
- `/home/ubuntu/.backups/apache-landscape-classic-query-20260704T223905Z`

`apache2ctl configtest` passed and Apache was reloaded after each edit.

## Validation

| Probe | Result |
|---|---|
| `curl -I https://landscape.atius.com.br/` | `302`, `Location: https://landscape.atius.com.br/account/standalone/secrets` |
| `curl -I 'https://landscape.atius.com.br/?next_url=%2Faccount%2Fstandalone%2Fsecrets'` | `200`, classic login callback preserved |
| `curl -L --max-redirs 4 https://landscape.atius.com.br/` | final URL `/?next_url=%2Faccount%2Fstandalone%2Fsecrets`, `200 text/html;charset=utf-8`, `redirects=3` |
| `curl -I https://landscape.atius.com.br/new_dashboard/overview` | `200`; modern dashboard remains reachable by direct URL |
| `curl -I http://landscape.atius.com.br/ping` | `200`; client ping remains intact |

## Operational Note

The modern dashboard is still available at `/new_dashboard/overview`, but it is
no longer the default landing path for `https://landscape.atius.com.br/`.
