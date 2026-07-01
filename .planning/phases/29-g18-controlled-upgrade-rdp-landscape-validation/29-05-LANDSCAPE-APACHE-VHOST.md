# Phase 29: Landscape Apache vhost correction

**Date:** 2026-06-25
**Host:** `atius-srv-1`
**Public endpoint:** `https://landscape.atius.com.br/`

## Problem

`landscape.atius.com.br` had DNS pointing to `atius-srv-1`, but Apache did not have an explicit vhost for the hostname. HTTPS/SNI therefore fell through to the default `*:443` vhost, `admin.atius.com.br`, causing wrong routing and confusing redirects/responses under the `admin` application.

## Fix applied

- Created explicit Apache vhost: `/etc/apache2/sites-available/landscape.atius.com.br.conf`.
- Enabled the site via `/etc/apache2/sites-enabled/landscape.atius.com.br.conf`.
- Issued a public Let's Encrypt certificate for `landscape.atius.com.br`.
- Configured port 80 redirect to HTTPS while preserving ACME challenge path.
- Configured port 443 with the Let's Encrypt certificate.
- Added a temporary static placeholder for all paths until Landscape self-hosted is installed.

## Important implementation detail

This host has a global certbot alias:

```apache
Alias /.well-known/acme-challenge/ /var/www/certbot/.well-known/acme-challenge/
```

The first certificate attempt using `/var/www/landscape.atius.com.br` as webroot failed with ACME 404. The successful issuance used `/var/www/certbot` as webroot.

## Result

- `https://landscape.atius.com.br/login?redirect=%2Fadmin` returns HTTP 200 from the Landscape placeholder, not from `admin.atius.com.br`.
- `http://landscape.atius.com.br/login?redirect=%2Fadmin` redirects to the same host over HTTPS.
- Certificate subject: `CN = landscape.atius.com.br`.
- Issuer: Let's Encrypt `YE2`.
- Expires: 2026-09-23.

## Backup

Remote backup directory:

```text
/home/ubuntu/.backups/apache-landscape-vhost-20260625T044645Z
```

## Next step

When Landscape self-hosted is installed, replace the static placeholder with the actual Landscape server reverse-proxy or native Landscape Apache config. Preserve the public hostname and certificate lineage unless the Landscape installer intentionally owns the vhost.
