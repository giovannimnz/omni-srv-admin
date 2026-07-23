# Phase 29: G18 Controlled Apt Upgrade Execution

**Execution window:** 2026-06-25T03:59Z to 2026-06-25T04:08Z
**Scope:** `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`
**Operator approval:** Full apt mutation approval received in chat for all hosts, including acceptance that all hosts are Ubuntu Pro/ESM enabled and that `pm2-ubuntu`/`k3s` absence is expected where applicable.

## Safety boundaries used

- Upgrades ran host-by-host, not in parallel.
- Command class used: `apt-get update` followed by `apt-get -y upgrade`.
- `apt full-upgrade`, `dist-upgrade`, `autoremove`, reboot, webhook POST, Ubuntu Pro attach/detach, and Landscape mutation were not executed.
- `NEEDRESTART_MODE=l` was used after `horistic-srv` to reduce automatic service restarts.
- Package config prompts used `--force-confdef` and `--force-confold` to preserve existing config where possible.

## Result summary

| Host | Pre upgradable | Post upgradable | Reboot required | Sensitive services after | Remote log | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `horistic-srv` | 20 | 0 | no | `landscape-client`, `xrdp`, `xrdp-sesman` active/enabled; `pm2-ubuntu`/`k3s` not-found as accepted | `/home/horistic/gsd-phase29-apt-upgrade-20260625T035935Z.log` | `needrestart` automatically restarted `xrdp.service`; post-check shows XRDP active. |
| `atius-srv-3` | 22 | 0 | no | `landscape-client`, `xrdp`, `xrdp-sesman`, `k3s` active/enabled; `pm2-ubuntu` not-found as accepted | `/home/ubuntu/gsd-phase29-apt-upgrade-20260625T040227Z.log` | No services needed restart. |
| `atius-srv-2` | 11 | 2 | no | `landscape-client`, `xrdp`, `xrdp-sesman`, `pm2-ubuntu`, `k3s` active/enabled | `/home/ubuntu/gsd-phase29-apt-upgrade-20260625T040335Z.log` | `kpartx` and `multipath-tools` deferred by Ubuntu phased updates. `xrdp.service` listed for restart, not restarted in defer/list mode. |
| `atius-srv-1` | 45 | 0 | no | `landscape-client`, `xrdp`, `xrdp-sesman`, `pm2-ubuntu`, `k3s` active/enabled | `/home/ubuntu/gsd-phase29-apt-upgrade-20260625T040504Z.log` | `webmin.service` listed for restart, not restarted in defer/list mode. Apt warned about old Sublime `.bak/.disabled` source-list filenames. AnyDesk service was re-enabled by package scripts. |

## Landscape SaaS post-upgrade evidence

`29-POST-UPGRADE-LANDSCAPE-API.md` confirms all 4 hosts are present in Landscape SaaS after the upgrade window.

## Post-upgrade inventory

`29-POST-UPGRADE-INVENTORY.md` confirms:

- `atius-srv-1`: 0 upgradable, reboot required: no.
- `atius-srv-2`: 2 upgradable, reboot required: no. Remaining packages are phased update deferrals.
- `atius-srv-3`: 0 upgradable, reboot required: no.
- `horistic-srv`: 0 upgradable, reboot required: no.

## Open items before Phase 29 completion

- Human RDP validation from Microsoft Remote Desktop for the managed hosts is still pending.
- Decide whether to restart deferred services later: `xrdp.service` on `atius-srv-2`, `webmin.service` on `atius-srv-1`, and `lightdm.service` on hosts where needrestart listed it as deferred.
- Decide whether to accept phased deferral on `atius-srv-2` or force phased packages later. Do not force now unless explicitly needed.
- Clean or rename old Sublime source-list backup files on `atius-srv-1` if desired.
- Decide whether to run `apt autoremove` on `atius-srv-1` for `libflac8` and `libopenh264-6`. Not run during this phase.
