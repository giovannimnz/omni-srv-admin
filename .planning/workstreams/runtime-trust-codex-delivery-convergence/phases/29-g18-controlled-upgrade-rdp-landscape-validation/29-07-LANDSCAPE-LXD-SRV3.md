# Phase 29 evidence - Landscape self-hosted in LXD on SRV3

Date: 2026-06-25

## Outcome

Landscape self-hosted was installed on `atius-srv-3` in an LXD container named `landscape`.

The public UI is currently published at:

- `https://landscape.atius.com.br/`

The public DNS record is:

- `landscape.atius.com.br A 137.131.190.161`
- Cloudflare proxy: disabled
- TTL: 300

The service still runs on SRV3. SRV1 is only the public TLS/reverse-proxy edge because OCI ingress on SRV3 blocks public TCP 80/443/6554.

## Installation details

- Host: `atius-srv-3`
- Host public IP: `136.248.126.12`
- Host private/VPN address used by SRV1: `10.1.1.3`
- Container: `landscape`
- Container image: `ubuntu:24.04`
- Container IPv4: `10.65.172.253`
- Landscape PPA: `ppa:landscape/self-hosted-24.04`
- Installed package: `landscape-server-quickstart`
- Installed Landscape server version observed in logs: `24.04.14-0landscape0`
- Timezone: `America/Recife`

The 24.04 LTS PPA was used because SRV3 is ARM64 and the 26.04 server/quickstart packages were not available for ARM64 during the preflight check. This keeps the deployment on an LTS channel supported for production.

## Remote logs

On `atius-srv-3`:

- `/home/ubuntu/gsd-phase29-landscape-lxd-20260625T051900Z.log`
- `/home/ubuntu/gsd-phase29-landscape-lxd-retry-20260625T051930Z.log`
- `/home/ubuntu/gsd-phase29-landscape-lxd-retry2-20260625T051945Z.log`
- `/home/ubuntu/gsd-phase29-landscape-certbot-20260625T052546Z.log`
- `/home/ubuntu/gsd-phase29-landscape-certbot-issue-20260625T052623Z.log`

The first two launch attempts failed before creating the container because `lxc` consumed the SSH heredoc stdin. The successful run redirected LXC command stdin from `/dev/null`.

## Public routing

SRV1 Apache vhost:

- `/etc/apache2/sites-available/landscape.atius.com.br.conf`

SRV1 backup:

- `/home/ubuntu/.backups/apache-landscape-proxy-20260625T052917Z`

SRV1 publishes:

- TCP 80: redirect to HTTPS
- TCP 443: Apache TLS termination using the existing Let's Encrypt certificate, then reverse proxy to `https://10.1.1.3/`
- TCP 6554: local `systemd-socket-proxyd` listener to `10.1.1.3:6554`

SRV1 6554 proxy units:

- `/etc/systemd/system/landscape-6554-proxy.socket`
- `/etc/systemd/system/landscape-6554-proxy.service`

SRV1 6554 backup:

- `/home/ubuntu/.backups/landscape-6554-proxy-20260625T053047Z`

## Validation evidence

Public HTTPS endpoint:

- `curl -I https://landscape.atius.com.br/` returned `HTTP/1.1 200 Ok`
- `Server: TwistedWeb/24.3.0`
- The root HTML title observed earlier was `New user - Landscape`
- The first-user form posts to `/new-standalone-user`

Container services observed active:

- `apache2`
- `postgresql`
- `rabbitmq-server`
- `landscape-appserver`
- `landscape-msgserver`

## Previously known gap - resolved 2026-06-25

Public TCP 6554 was initially blocked by OCI ingress even though SRV1 already had a listener and forwarder.

Resolution:

- Created OCI NSG `landscape-6554-srv1`.
- Added stateful ingress TCP `6554` from `0.0.0.0/0`.
- Attached the NSG only to the SRV1 primary VNIC.
- External TCP probe to `137.131.190.161:6554` now succeeds.

SRV3 public ingress is also blocked for 80/443/6554, which is why direct Let's Encrypt issuance inside the container failed with a timeout against `136.248.126.12:80`.

## Initial user state

No admin user/password was created by automation.

The deployed Landscape instance is in first-user bootstrap mode at `https://landscape.atius.com.br/`. The owner should create the first user via the web form using their chosen passphrase.
