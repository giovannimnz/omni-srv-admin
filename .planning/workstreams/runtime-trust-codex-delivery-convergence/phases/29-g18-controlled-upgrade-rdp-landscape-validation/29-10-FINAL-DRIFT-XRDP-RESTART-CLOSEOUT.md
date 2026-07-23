# Phase 29 evidence - final drift cleanup and XRDP restart closeout

Date: 2026-06-25

## Operator decision

Operator confirmed:

- Microsoft RDP interactive login is confirmed.
- XRDP restarts are approved on all hosts.
- Remaining apt drift can be handled normally.

## XRDP restart window

XRDP was restarted host by host:

1. `atius-srv-1`
2. `atius-srv-2`
3. `atius-srv-3`
4. `horistic-srv`

Remote logs:

- `/home/ubuntu/gsd-phase29-xrdp-restart-20260625T193856Z.log`
- `/home/horistic/gsd-phase29-xrdp-restart-20260625T193856Z.log`

Result:

| Host | `xrdp` | `xrdp-sesman` | TCP 3389 |
| --- | --- | --- | --- |
| `atius-srv-1` | active/enabled | active/enabled | open |
| `atius-srv-2` | active/enabled | active/enabled | open |
| `atius-srv-3` | active/enabled | active/enabled | open |
| `horistic-srv` | active/enabled | active/enabled | open |

## Final apt drift cleanup

Final drift packages applied:

| Host | Packages |
| --- | --- |
| `atius-srv-1` | `firefox`, `mongodb-mongosh` |
| `atius-srv-2` | `firefox` |
| `atius-srv-3` | `firefox` |
| `horistic-srv` | `firefox` |

Remote logs:

- `/home/ubuntu/gsd-phase29-final-apt-drift-20260625T193935Z.log`
- `/home/horistic/gsd-phase29-final-apt-drift-20260625T193935Z.log`

No reboot was performed.

No PM2 restart, K3s restart, Landscape mutation, webhook POST, or broad service restart was performed.

## Final smoke

| Host | Reboot required | Upgradable count | XRDP | PM2 | Landscape client | K3s |
| --- | --- | ---: | --- | --- | --- | --- |
| `atius-srv-1` | no | 0 | active/enabled | active/enabled | active/enabled | active/enabled |
| `atius-srv-2` | no | 0 | active/enabled | active/enabled | active/enabled | active/enabled |
| `atius-srv-3` | no | 0 | active/enabled | active/enabled | active/enabled | active/enabled |
| `horistic-srv` | no | 0 | active/enabled | active/enabled | active/enabled | `k3s-agent` active/enabled |

Public/network checks:

- `10.1.1.1:3389`: open
- `10.1.1.2:3389`: open
- `10.1.1.3:3389`: open
- `10.1.1.4:3389`: open
- `137.131.190.161:6554`: open
- `https://landscape.atius.com.br/`: responds through SRV1 edge
- `https://portainer.atius.com.br/`: HTTP 401 expected
- `https://docker.atius.com.br/`: HTTP 401 expected

K3s nodes:

- `atius-srv-1`: Ready, `control-plane,etcd`
- `atius-srv-2`: Ready, `control-plane,etcd`
- `atius-srv-3`: Ready, `control-plane,etcd`
- `horistic-srv`: Ready, agent

## Remaining warnings

Phase 29 is operationally complete.

Warnings deferred to later phases:

- Observability remains yellow.
- SRV1/SRV2 root disks previously observed at 86%.
- Some desktop user sessions may still need browser/session restart after Firefox updates; no session cleanup was performed.
