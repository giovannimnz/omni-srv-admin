---
phase: 29
date: 2026-07-04
status: applied
scope: landscape-cloudflare-proxy-cert-repair
---

# Landscape Cloudflare Proxy and Certificate Repair

## Symptom

`https://landscape.atius.com.br/` was blocked by Brave with
`net::ERR_CERT_AUTHORITY_INVALID` under HSTS.

## Root Cause

Two live drifts combined:

- Cloudflare DNS record `A landscape.atius.com.br -> 137.131.190.161` was still
  DNS-only (`proxied=false`), so browsers connected directly to SRV1.
- `/etc/apache2/sites-available/landscape.atius.com.br.conf` existed, but the
  site was not enabled under `/etc/apache2/sites-enabled/`. Apache therefore
  fell through to the default `admin.atius.com.br` vhost on `*:443`.

The default vhost presented the Cloudflare Origin CA certificate directly to
the browser. That certificate is valid for Cloudflare-to-origin traffic, but is
not trusted by normal browser root stores when served DNS-only.

## Changes Applied

On `atius-srv-1`:

- Backed up the Landscape Apache vhost to
  `/home/ubuntu/.backups/apache-landscape-enable-20260704T214537Z`.
- Enabled the Apache site with `a2ensite landscape.atius.com.br.conf`.
- Ran `apache2ctl configtest`.
- Reloaded Apache.

In Cloudflare:

- Patched DNS record `7eedc66a6420a7beb1f5cb9abb84a94c`.
- Before: `A landscape.atius.com.br -> 137.131.190.161`, `proxied=false`,
  `ttl=300`.
- After: `A landscape.atius.com.br -> 137.131.190.161`, `proxied=true`,
  `ttl=1`.
- API before/after evidence is stored on SRV1 at
  `/home/ubuntu/.backups/cloudflare-landscape-proxy-20260704T214747Z`.

No Cloudflare credentials or secret values were written to repo docs.

## Validation

Public probes after the fix:

| Probe | Result |
|---|---|
| `Resolve-DnsName landscape.atius.com.br -Type A` | Cloudflare IPs `104.21.42.188`, `172.67.208.94` |
| `curl -I https://landscape.atius.com.br/` | `302 Found`, `Server: cloudflare`, `Location: /new_dashboard/` |
| `curl -I https://landscape.atius.com.br/new_dashboard/overview` | `200 OK`, `Server: cloudflare`, `Content-Type: text/html` |
| `curl -I https://landscape.atius.com.br/assets/atius-dark.css` | `200 OK`, `Content-Type: text/css` |
| `curl -i http://landscape.atius.com.br/ping` | `200 OK`, `Server: cloudflare` |
| TLS edge certificate | `CN=atius.com.br`, issuer `Google Trust Services WE1` |
| TLS origin certificate after Apache enablement | `CN=landscape.atius.com.br`, issuer `Let's Encrypt YE2` |

## Residual

The SRV1 origin socket for Landscape TCP `6554` remains reachable directly:

- `137.131.190.161:6554`: open

The proxied hostname no longer exposes arbitrary TCP `6554`:

- `landscape.atius.com.br:6554`: timeout through Cloudflare orange-cloud DNS

If a future Landscape client path needs raw TCP `6554` by hostname, publish a
separate DNS-only hostname, use the direct origin IP, or configure Cloudflare
Spectrum before depending on hostname-based TCP `6554`.
