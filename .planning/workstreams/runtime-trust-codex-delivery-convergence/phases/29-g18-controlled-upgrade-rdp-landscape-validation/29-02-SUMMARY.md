# Phase 29 Task 02 summary

Date: 2026-06-25

## Result

Phase 29 validation artifacts are complete and Phase 29 is operationally complete.

## Completed

- Ran read-only G18 regression watchdog.
- Confirmed all four hosts reachable on SSH.
- Confirmed TCP 3389 open on all four hosts.
- Confirmed Ubuntu Pro attached and ESM Apps enabled on all four hosts.
- Confirmed no reboot marker on all four hosts.
- Confirmed `landscape-client`, `xrdp`, `xrdp-sesman`, `pm2-ubuntu` active/enabled on all four hosts.
- Confirmed K3s has four Ready nodes: SRV1/SRV2/SRV3 control-plane+etcd and Horistic agent.
- Confirmed Portainer pod/service are running.
- Confirmed public edges answer for Landscape, Portainer, and Docker.
- Confirmed Landscape SaaS online evidence exists for all four hosts.
- Installed and published Landscape self-hosted on SRV3 LXD during the extended Phase 29 work.
- Opened Landscape TCP 6554 on the SRV1 public edge through a scoped OCI NSG.
- Applied second apt window for `xrdp`, Chromium, and SRV2 phased packages.
- Restarted XRDP services host by host after operator approval.
- Applied final apt drift cleanup; all four hosts now report `upgradable_count=0`.

## Warnings deferred after Phase 29

| Warning | Impact | Next action |
| --- | --- | --- |
| Observability yellow | Not a hard outage, but not green | Investigate 1 unhealthy target, 18 firing alerts, and missing dashboards in governance/observability follow-up. |
| SRV1/SRV2 root disk at 86% | Capacity warning | Schedule cleanup or capacity action. |
| Desktop browser/session restarts after Firefox update | Existing desktop sessions may still run old browser binaries | User/session restart if needed; no session cleanup was performed. |

## Requirement status

| Requirement | State |
| --- | --- |
| G18-02 | PASS |
| G18-03 | PASS |
| G18-04 | PASS |
| G18-05 | PASS_WITH_WARNINGS |

## Safety statement

No XRDP restart, PM2 repair, webhook POST, reboot, Landscape enrollment mutation, package mutation, or broad service restart was performed during Task 02 validation.

## Recommended next step

Advance to Phase 30: Landscape/Omni Governance Operating Model.
