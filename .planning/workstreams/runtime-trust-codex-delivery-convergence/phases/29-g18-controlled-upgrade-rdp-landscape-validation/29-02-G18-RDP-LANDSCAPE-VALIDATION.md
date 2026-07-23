# Phase 29 Task 02: RDP and Landscape validation record

Date: 2026-06-25

## Requirement state

| Requirement | State | Evidence |
| --- | --- | --- |
| G18-02 | PASS | Controlled apt upgrade ran on all four hosts with approval and per-host logs in `29-03-G18-UPGRADE-EXECUTION.md`. Second and final apt windows remediated all known upgradable drift; final `upgradable_count=0` on all four hosts. |
| G18-03 | PASS | Operator confirmed Microsoft RDP interactive desktop login. XRDP services were restarted host by host and TCP 3389 stayed open on all four hosts. |
| G18-04 | PASS | Landscape SaaS API evidence and operator statement confirm all four hosts online. Landscape self-hosted is also now installed on SRV3 LXD and published at `https://landscape.atius.com.br/`. |
| G18-05 | PASS_WITH_WARNINGS | Watchdog and final smoke ran. Warnings remain for observability yellow and disk 86% on SRV1/SRV2; these are deferred. |

## Microsoft RDP validation

| Host | TCP 3389 | Interactive Microsoft RDP login | State |
| --- | --- | --- | --- |
| `atius-srv-1` | open | confirmed by operator | PASS |
| `atius-srv-2` | open | confirmed by operator | PASS |
| `atius-srv-3` | open | confirmed by operator | PASS |
| `horistic-srv` | open | confirmed by operator | PASS |

XRDP restart was later approved by the operator and executed host by host. No session cleanup, display change, or socket cleanup was performed.

## Landscape validation

### SaaS

State: PASS.

Evidence:

- `29-POST-UPGRADE-LANDSCAPE-API.md` confirms all four expected hosts are present in Landscape SaaS after the upgrade window.
- Operator supplied dashboard evidence showing `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and `horistic-srv` online in Landscape SaaS.

### Self-hosted

State: PASS.

Evidence:

- Landscape self-hosted installed in LXD container `landscape` on `atius-srv-3`.
- Public URL `https://landscape.atius.com.br/` reaches the Landscape bootstrap UI through SRV1 reverse proxy.
- Container services observed active: `apache2`, `postgresql`, `rabbitmq-server`, `landscape-appserver`, `landscape-msgserver`.
- First-user bootstrap is expected; no default username/password exists.

TCP 6554:

- OCI ingress was opened with a scoped NSG attached only to the SRV1 VNIC.
- Public TCP probe to `137.131.190.161:6554` now succeeds.

## Regression summary

See `29-02-G18-REGRESSION-WATCHDOG.md`.

Key points:

- Pro/ESM attached and `esm-apps=enabled` on all four hosts.
- No reboot marker on any host.
- XRDP active/enabled on all four hosts.
- PM2 active/enabled on all four hosts.
- K3s has all four nodes Ready; Horistic is joined as an agent.
- Portainer is running and public edges answer behind auth.
- Observability is operational but not fully green.
- Phase 29 package drift was remediated and `xrdp`/`xrdp-sesman` were restarted in a controlled host-by-host window.

## Human checkpoint

Operator confirmed Microsoft RDP interactive login on all four hosts.
