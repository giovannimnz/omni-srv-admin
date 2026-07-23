# Phase 29 Task 02: G18 regression watchdog

Date: 2026-06-25

## Scope and safety

This watchdog was read-only.

Explicitly not executed:

- No XRDP restart
- No PM2 repair
- No webhook POST
- No reboot
- No Landscape enrollment mutation
- No `apt upgrade`, `apt full-upgrade`, `apt autoremove`, or package install/remove
- No broad service restart

## Summary

| Area | Status | Evidence |
| --- | --- | --- |
| SSH reachability | PASS | All four managed hosts responded to SSH probes. |
| RDP TCP reachability | PASS | TCP 3389 open on `10.1.1.1`, `10.1.1.2`, `10.1.1.3`, `10.1.1.4`. |
| Human Microsoft RDP login | PASS | Operator confirmed Microsoft RDP interactive login after Phase 29 changes. |
| Ubuntu Pro / ESM Apps | PASS | `pro status --format json` reported `attached=True`; `esm-apps=enabled` on all four hosts. |
| Reboot marker | PASS | `/var/run/reboot-required` absent on all four hosts. |
| Landscape SaaS | PASS | Existing post-upgrade API evidence shows all four hosts present; operator previously reported all online in Landscape SaaS. |
| Landscape self-hosted | PASS | `https://landscape.atius.com.br/` reaches Landscape self-hosted bootstrap UI through SRV1 reverse proxy to SRV3 LXD. TCP 6554 is open through SRV1 OCI NSG and socket proxy. |
| XRDP services | PASS_WITH_DEFERRED_RESTART | `xrdp` and `xrdp-sesman` active/enabled on all four hosts; `xrdp` ESM package update installed on all four, but `needrestart` recommends a controlled service restart. |
| PM2 service | PASS | `pm2-ubuntu` active/enabled on all four hosts after runtime repair. |
| K3s | PASS | SRV1/SRV2/SRV3 Ready as `control-plane,etcd`; `horistic-srv` Ready as agent. |
| Portainer | PASS | Portainer pod `1/1 Running`; public Portainer/Docker edges return HTTP 401 behind auth. |
| Apache/public edges | PASS | `landscape.atius.com.br`, `portainer.atius.com.br`, and `docker.atius.com.br` respond. |
| Disk posture | WARN | SRV1 and SRV2 root disks at 86%; SRV3 64%; Horistic 38%. |
| Observability | WARN | `omni srv observability status --json`: K3s green, Loki green, Alertmanager green, Prometheus yellow, dashboards yellow. |
| Apt drift after upgrade | PASS | Final apt drift cleanup completed; `apt list --upgradable` count is 0 on all four hosts. |

## Host matrix

| Host | Reboot required | Apt upgradable | Pro attached | ESM Apps | Landscape client | XRDP | PM2 | K3s role | Disk |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| `atius-srv-1` | no | 4 | true | enabled | registered; active/enabled | active/enabled | active/enabled | control-plane,etcd | 86% used, 28G available |
| `atius-srv-2` | no | 6 | true | enabled | registered; active/enabled | active/enabled | active/enabled | control-plane,etcd | 86% used, 28G available |
| `atius-srv-3` | no | 4 | true | enabled | registered; active/enabled | active/enabled | active/enabled | control-plane,etcd | 64% used, 71G available |
| `horistic-srv` | no | 4 | true | enabled | registered; active/enabled | active/enabled | active/enabled | k3s-agent | 38% used, 61G available |

## Pending apt packages before second apt window

`atius-srv-1`:

- `chromium`
- `chromium-common`
- `chromium-sandbox`
- `xrdp` from `noble-apps-security`

## Second apt window result

See `29-09-SECOND-APT-WINDOW-XRDP-CHROMIUM.md`.

The following were updated on all four hosts:

- `xrdp` to `0.9.24-4ubuntu0.1~esm1`
- `chromium`, `chromium-common`, `chromium-sandbox` to `149.0.7827.196-1xtradeb1.2404.1`

The following were updated on SRV2:

- `kpartx` to `0.9.4-5ubuntu8.2`
- `multipath-tools` to `0.9.4-5ubuntu8.2`

Remaining upgradable packages after the final drift cleanup:

- `atius-srv-1`: none
- `atius-srv-2`: none
- `atius-srv-3`: none
- `horistic-srv`: none

`atius-srv-2`:

- `chromium`
- `chromium-common`
- `chromium-sandbox`
- `kpartx`
- `multipath-tools`
- `xrdp` from `noble-apps-security`

`atius-srv-3`:

- `chromium`
- `chromium-common`
- `chromium-sandbox`
- `xrdp` from `noble-apps-security`

`horistic-srv`:

- `chromium`
- `chromium-common`
- `chromium-sandbox`
- `xrdp` from `noble-apps-security`

## RDP TCP check

| Host | TCP 3389 |
| --- | --- |
| `atius-srv-1` / `10.1.1.1` | open |
| `atius-srv-2` / `10.1.1.2` | open |
| `atius-srv-3` / `10.1.1.3` | open |
| `horistic-srv` / `10.1.1.4` | open |

This is not a substitute for Microsoft RDP interactive login validation.

## K3s evidence

`sudo k3s kubectl get nodes -o wide` on SRV1 reported:

| Node | Status | Roles | Version | Internal IP |
| --- | --- | --- | --- | --- |
| `atius-srv-1` | Ready | control-plane,etcd | v1.35.5+k3s1 | 10.1.1.1 |
| `atius-srv-2` | Ready | control-plane,etcd | v1.35.5+k3s1 | 10.1.1.2 |
| `atius-srv-3` | Ready | control-plane,etcd | v1.35.5+k3s1 | 10.1.1.7 |
| `horistic-srv` | Ready | none | v1.35.5+k3s1 | 10.1.1.4 |

Portainer:

- `pod/portainer-65c5dc8f57-czbns`: `1/1 Running`
- `service/portainer`: `ClusterIP`, ports `9443/TCP`, `8000/TCP`

## Public edge evidence

| URL | Result |
| --- | --- |
| `https://landscape.atius.com.br/` | HTTP 303/200 bootstrap flow from Landscape self-hosted via SRV1 edge |
| `https://portainer.atius.com.br/` | HTTP 401, expected edge auth |
| `https://docker.atius.com.br/` | HTTP 401, expected edge auth |
| `137.131.190.161:6554` | TCP open |

## Observability evidence

`python3 -m cli.omni srv observability status --json` reported:

- `k3s`: green, cluster reachable
- `loki`: green, ready endpoint 200
- `alertmanager`: green, healthy endpoint 200
- `prometheus-rules`: green, 35 rules loaded
- `prometheus`: yellow, 26/27 targets up, 18 firing alerts
- `dashboards`: yellow, missing `jenkins-gdrive`, `k3s-ha`, `pm2-fleet`, `portainer`

## Closure impact

G18-05 watchdog execution is complete, but Phase 29 should not be marked fully complete until:

1. Observability yellow is deferred to a later governance/observability phase.
2. SRV1/SRV2 disk warning is deferred to a cleanup/capacity phase.
