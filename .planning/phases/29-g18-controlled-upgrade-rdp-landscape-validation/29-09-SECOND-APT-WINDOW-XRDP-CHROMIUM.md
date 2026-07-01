# Phase 29 evidence - second apt window for XRDP/Chromium drift

Date: 2026-06-25

## Outcome

A second controlled apt window was executed to remove the known Phase 29 package drift for:

- `xrdp` ESM security update on all four hosts
- `chromium`, `chromium-common`, `chromium-sandbox` on all four hosts
- SRV2 phased packages `kpartx` and `multipath-tools`

No reboot was performed.

No manual XRDP restart, PM2 restart, K3s restart, Landscape mutation, webhook POST, or broad service restart was performed.

## Safety mode

Commands used:

- `apt-get update`
- `apt-get install --only-upgrade ...`

Options used:

- `DEBIAN_FRONTEND=noninteractive`
- `NEEDRESTART_MODE=l`
- `Dpkg::Options::=--force-confdef`
- `Dpkg::Options::=--force-confold`
- `APT::Get::Always-Include-Phased-Updates=true`

## Host results

| Host | Updated packages | Reboot required | Service status after | Remote log |
| --- | --- | --- | --- | --- |
| `atius-srv-1` | `xrdp`, `chromium`, `chromium-common`, `chromium-sandbox` | no | `xrdp`, `xrdp-sesman`, `pm2-ubuntu`, `landscape-client`, `k3s` active/enabled | `/home/ubuntu/gsd-phase29-second-apt-window-20260625T191110Z.log` |
| `atius-srv-2` | `xrdp`, `chromium`, `chromium-common`, `chromium-sandbox`, `kpartx`, `multipath-tools` | no | `xrdp`, `xrdp-sesman`, `pm2-ubuntu`, `landscape-client`, `k3s` active/enabled | `/home/ubuntu/gsd-phase29-second-apt-window-20260625T191110Z.log` |
| `atius-srv-3` | `xrdp`, `chromium`, `chromium-common`, `chromium-sandbox` | no | `xrdp`, `xrdp-sesman`, `pm2-ubuntu`, `landscape-client`, `k3s` active/enabled | `/home/ubuntu/gsd-phase29-second-apt-window-20260625T191110Z.log` |
| `horistic-srv` | `xrdp`, `chromium`, `chromium-common`, `chromium-sandbox` | no | `xrdp`, `xrdp-sesman`, `pm2-ubuntu`, `landscape-client`, `k3s-agent` active/enabled | `/home/horistic/gsd-phase29-second-apt-window-20260625T191110Z.log` |

## Version evidence

All four hosts now report:

- `xrdp`: `0.9.24-4ubuntu0.1~esm1`
- `chromium`: `149.0.7827.196-1xtradeb1.2404.1`
- `chromium-common`: `149.0.7827.196-1xtradeb1.2404.1`
- `chromium-sandbox`: `149.0.7827.196-1xtradeb1.2404.1`
- `kpartx`: `0.9.4-5ubuntu8.2`
- `multipath-tools`: `0.9.4-5ubuntu8.2`

## Network/service smoke

Post-window TCP checks:

- `10.1.1.1:3389`: open
- `10.1.1.2:3389`: open
- `10.1.1.3:3389`: open
- `10.1.1.4:3389`: open
- `137.131.190.161:6554`: open

K3s nodes:

- `atius-srv-1`: Ready, `control-plane,etcd`
- `atius-srv-2`: Ready, `control-plane,etcd`
- `atius-srv-3`: Ready, `control-plane,etcd`
- `horistic-srv`: Ready, agent

## Important XRDP note

`needrestart` reported that `xrdp` and `xrdp-sesman` should be restarted to load the updated binaries.

This was deliberately not done in this window because restarting XRDP can drop active RDP sessions. A separate operator-confirmed RDP restart window is still required if the security update must be activated immediately.

## Remaining package drift outside this window

The following packages remain upgradable after this controlled window:

| Host | Remaining upgradable packages |
| --- | --- |
| `atius-srv-1` | `firefox`, `mongodb-mongosh` |
| `atius-srv-2` | `firefox` |
| `atius-srv-3` | `firefox` |
| `horistic-srv` | `firefox` |

These were not part of the Phase 29 G18 `xrdp`/Chromium remediation scope.

## Residual blockers

- Operator Microsoft RDP interactive login validation is still required.
- Decide whether to run an XRDP service restart window.
- Observability remains yellow.
- SRV1/SRV2 root disks remain at 86%.
