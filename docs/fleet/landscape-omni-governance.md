# Landscape / Omni Governance Operating Model

**Date:** 2026-06-25  
**Scope:** Landscape self-hosted, Landscape SaaS fallback, Omni Fleet, Cockpit, K3s/Portainer and observability for the managed servers: `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`.

## Decision

Omni Fleet remains the central source of truth for reviewed inventory, governance, audit and approved automation.

Landscape self-hosted is the durable Ubuntu machine-management UI for this fleet. Landscape SaaS remains a fallback and validation reference, not the durable endpoint.

Cockpit remains a host-level break-glass console only.

K3s and Portainer remain the Kubernetes/container workload administration plane.

Observability remains the read-only signal plane for metrics, logs, alerts and dashboards.

No console should be treated as a replacement for the others. The operating model is layered deliberately to avoid duplicate control planes.

## Responsibility Matrix

| Capability | Primary owner | Secondary / fallback | Not allowed |
|---|---|---|---|
| Reviewed host identity | Omni Fleet inventory in `inventory/hosts/*.yaml` | `DbOmniFleet` runtime projection | Landscape or Portainer becoming identity source of truth |
| Runtime fleet state | `DbOmniFleet` via PgBouncer | Landscape self-hosted UI/API for Ubuntu-machine status | Direct PostgreSQL from nodes |
| Ubuntu package visibility | Landscape self-hosted | Omni collectors in Phase 31 | Cockpit as fleet compliance plane |
| Ubuntu package mutation | Landscape activities or approved Omni update plans | Manual apt only under explicit gate | Automatic background patching without audit |
| Ubuntu Pro / ESM state | Landscape + `pro` client on each host | Omni watchdog/regression docs | Token material in repo/docs/logs |
| Desired-state profiles | Omni Fleet Phase 31 | Landscape repository/package profiles when useful | Drift remediation outside approved plans |
| CVE / USN prioritization | Phase 32 Omni/Landscape parity | `pro security-status`, Landscape package alerts | Manual guesswork without host evidence |
| Host shell / service break-glass | Cockpit over protected path or SSH/VPN | Direct SSH via WireGuard | Anonymous public `:9090` |
| Kubernetes workloads | K3s + Portainer | `kubectl` on approved admin hosts | Landscape managing pods/workloads |
| Container UI | Portainer | K3s CLI/Helm manifests | Cockpit or Landscape as workload controller |
| Metrics/logs/alerts | Observability stack | Host-local logs and Landscape events | Observability initiating repairs automatically |
| DNS/edge publication | Cloudflare + Apache runbooks | OCI ingress/NSG where needed | Exposing admin consoles directly without gate |
| Audit trail | Omni `TbAuditEvents`, phase docs and Obsidian infra notes | Landscape activities/events | Secrets in audit messages |

## Access Model

| Surface | Public URL / path | Required gate | Current posture |
|---|---|---|---|
| Landscape self-hosted | `https://landscape.atius.com.br/` | Cloudflare proxied HTTPS edge -> SRV1 Apache proxy -> SRV3 Landscape LXD | Live; root lands on classic `/account/standalone/secrets` so Vault/secrets administration is the default |
| Landscape modern dashboard | `https://landscape.atius.com.br/new_dashboard/overview` | Same edge path; direct URL only | Live, but not the default landing path |
| Landscape client ping | `http://landscape.atius.com.br/ping` | Cloudflare proxied HTTP edge -> SRV1 Apache `/ping` exception -> Landscape quickstart `/ping`; do not redirect this path to HTTPS | Live, required by Landscape client |
| Landscape SaaS | `https://landscape.canonical.com/` | Canonical login | Fallback/reference only after migration |
| Portainer | `https://portainer.atius.com.br/` | Apache Basic Auth now; Cloudflare Access once account-level Access is enabled | Live, pre-Access state |
| Docker/Portainer edge alias | `https://docker.atius.com.br/` | Same admin edge gate as Portainer | Live, pre-Access state |
| Cockpit | `https://cockpit.atius.com.br/` if published | Cloudflare Access, Apache auth/SSO or WireGuard-only | Break-glass only; direct `:9090` must not be anonymous-public |
| Omni Fleet CLI | Local repo + controlled SSH/VPN | Operator shell access and PgBouncer-only DB path | Source of governance/audit |
| Observability | Grafana/Prometheus/Loki/Alertmanager endpoints | Admin edge gate; webhook secrets root-only | Partially live/yellow per Phase 17 |

Cloudflare Access is still blocked until the account-level Access product is enabled in the Cloudflare dashboard. Until then, Apache Basic Auth, SSH/VPN and service-specific auth remain the active gates.

## Operating Rules

1. Landscape self-hosted is allowed to execute Ubuntu-machine actions, but high-risk actions still need an operator checkpoint when they can affect RDP, K3s, PM2, Apache, trading workloads or reboot state.
2. Omni Fleet is the place where desired state, drift, update approval and audit are modeled. Landscape can provide machine evidence and activity execution, but it does not own fleet policy.
3. Cockpit is only for host-level emergency inspection or manual repair. It must not become the package compliance system or central automation plane.
4. K3s and Portainer own cluster/workload administration. Landscape and Cockpit must not be used as Kubernetes workload controllers.
5. Observability is read-only by default. Alerting can page or open an incident, but repair execution must flow through a documented guard/update plan.
6. Secrets stay out of repo, docs, `.planning`, logs and Obsidian. Use root-only files or secret references.
7. Any live mutation that changes edge exposure, authentication, package state, reboot behavior, XRDP/RDP, PM2, K3s or webhook side effects needs an explicit gate and rollback note.

## Omni Landscape CLI Bridge

The repo exposes a Landscape bridge:

```bash
PYTHONPATH=cli python3 -m omni landscape --help
```

Purpose:

- Keep script source, version, hash, risk and host scope reviewed in `omni-srv-admin`.
- Sync those scripts into Landscape with `omni landscape scripts sync --yes`.
- Execute them across all managed hosts with `omni landscape run <script> --hosts all --yes`.
- Use Landscape activity tracking as the delivery/audit surface.

Canonical runbook:

- `docs/fleet/landscape-omni-cli.md`

Versioned script registry:

- `modules/landscape-control-plane/scripts/manifest.json`

## Fallback Model

| Failure | First fallback | Second fallback | Notes |
|---|---|---|---|
| Landscape self-hosted UI down | SSH/VPN + Omni Fleet read-only status | Landscape SaaS re-registration from client backups | Client SaaS rollback backups exist under `/var/backups/landscape-client-saas-*` on each host |
| Landscape self-hosted LXD container broken | LXD backup/snapshot and Vault bootstrap paths | Rebuild quickstart in LXD on SRV3 or another host | Do not lose `/root/landscape-vault-init.json` or registration key material |
| SRV1 public proxy down | Direct VPN to SRV3/LXD for admin repair | Move Cloudflare DNS/OCI ingress directly to SRV3 | DNS currently points public Landscape to SRV1 behind Cloudflare proxy |
| Cloudflare Access unavailable | Apache Basic Auth or WireGuard-only | Service disabled/blocked public-side | No direct anonymous admin console exposure |
| PgBouncer/DbOmniFleet unavailable | Local Omni heartbeat/cache and Landscape status | Host-local SSH checks | Nodes must not bypass PgBouncer to direct PostgreSQL |
| Portainer unavailable | `kubectl`/Helm on admin host | K3s restore/runbook | Landscape is not the fallback for workloads |
| Observability degraded | Landscape events + host logs | Manual `systemctl`, `journalctl`, K3s probes | Observability yellow does not block governance docs |

## Current Live Baseline

| Item | State |
|---|---|
| Managed servers | `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv` |
| Landscape self-hosted | LXD container `landscape` on `atius-srv-3` |
| Landscape public edge | Cloudflare proxied DNS -> SRV1 Apache reverse proxy -> SRV3 |
| Landscape default UI | Classic `/account/standalone/secrets`; modern dashboard remains direct-link only |
| Landscape TCP 6554 | SRV1 socket proxy to SRV3, OCI NSG scoped to SRV1; direct origin `137.131.190.161:6554` remains open, but `landscape.atius.com.br:6554` is not available while the hostname is Cloudflare proxied |
| Landscape clients | Five managed hosts target the self-hosted account `standalone`; refresh `accepted/pending` through the Landscape API before using the count as evidence |
| Landscape secrets | Local HashiCorp Vault on `127.0.0.1:8200`, `landscape-secrets-service` token present |
| K3s | Four nodes Ready from Phase 29 closeout |
| Portainer | Public edge live with admin gate fallback |
| Observability | Yellow; Phase 17 follow-ups still pending |
| Cloudflare Access | Code/runbook ready; account dashboard enablement still blocked |

## Validation Commands

Read-only checks:

```bash
sudo landscape-config --is-registered
curl -sSI https://landscape.atius.com.br/ | grep -i 'server: cloudflare\|location:.*account/standalone/secrets'
curl -sSI 'https://landscape.atius.com.br/?next_url=%2Faccount%2Fstandalone%2Fsecrets' | head -1
curl -sS -o /dev/null -w '%{http_code}\n' http://landscape.atius.com.br/ping
curl -sS -o /dev/null -w '%{http_code}\n' https://landscape.atius.com.br/message-system
PYTHONPATH=cli python3 -m omni fleet monitor hosts --json
PYTHONPATH=cli python3 -m omni srv observability status --json
python3 scripts/validate-edge-auth.py --expect pre-cutover
```

Server-side Landscape self-hosted checks:

```bash
ssh ubuntu@10.13.1.13 'lxc exec landscape -- systemctl is-active vault landscape-secrets-service landscape-appserver landscape-msgserver landscape-pingserver'
ssh ubuntu@10.13.1.13 'lxc exec landscape -- curl -sS http://127.0.0.1:26155/ | jq -r ".token != null"'
```

## Phase Ownership

| Phase | Ownership |
|---|---|
| Phase 30 | Responsibility matrix, access model and fallback runbook |
| Phase 31 | Omni collectors and desired-state profiles |
| Phase 32 | CVE/USN and Landscape parity reporting |
| Phase 33+ | Domain Infrastructure with FreeIPA/Keycloak/Samba |
| Phase 37+ | Production Guard for ATS/Horistic |
