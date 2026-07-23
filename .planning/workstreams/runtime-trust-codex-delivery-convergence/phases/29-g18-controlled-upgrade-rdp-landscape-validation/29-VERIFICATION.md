---
phase: 29
status: passed
verified: 2026-06-26
---

# Phase 29 Verification

## Passed Checks

| Check | Result |
|---|---|
| Controlled apt execution | `29-03-G18-UPGRADE-EXECUTION.md` records staged host-by-host upgrades with explicit approval scope and no uncontrolled reboot/full-upgrade/autoremove |
| Final package drift | `29-02-SUMMARY.md` records final `upgradable_count=0` on `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and `horistic-srv` |
| Microsoft RDP validation | `29-02-G18-RDP-LANDSCAPE-VALIDATION.md` records operator-confirmed Microsoft RDP success on all four hosts |
| Landscape SaaS validation | `29-02-G18-RDP-LANDSCAPE-VALIDATION.md` plus `29-POST-UPGRADE-LANDSCAPE-API.md` confirm all four hosts online |
| Landscape self-hosted closure | Extended Phase 29 work published self-hosted Landscape at `https://landscape.atius.com.br/` with OCI ingress `6554` fixed by scoped SRV1 NSG |
| Regression watchdog | `29-02-G18-REGRESSION-WATCHDOG.md` covers apt, ESM, RDP/XRDP, Landscape, PM2, K3s, Apache edges, disk and observability without destructive repair |
| Requirement status | `G18-02`, `G18-03`, `G18-04` = `PASS`; `G18-05` = `PASS_WITH_WARNINGS` |

## Residual Warnings

These warnings were explicitly deferred and do not block Phase 29 closeout:

- observability remains yellow, not fully green
- root disks on `atius-srv-1` and `atius-srv-2` remain around `86%`
- some desktop/browser sessions may still require user-side restart after package refresh

## Requirement Closure

Phase 29 is verified as complete for the G18 controlled-upgrade closeout:

- controlled upgrade window executed with approvals
- RDP/XRDP validated on all four hosts
- Landscape SaaS confirmed online on all four hosts
- regression evidence captured without unauthorized repair actions
