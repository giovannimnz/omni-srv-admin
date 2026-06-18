---
phase: 14-resource-governor-pm2-boot-hardening
status: complete
started: 2026-06-15
completed: 2026-06-15
plans_total: 6
plans_complete: 6
plans_gated: 0
---

# Phase 14 Summary — Resource Governor + PM2 Boot Hardening

**All 6 plans complete. M006 closed. Live state preserved (no PM2/XRDP restart performed).**

## Performance

- **Phase duration:** ~2 hours (08:51 → 11:30 BRT)
- **Plans:** 6 of 6 complete
- **Live mutations:** 2 (Jenkins fix in 14-05, Jenkins K8s agent in 14-06)
- **Gated work deferred:** 14-02/14-03 live work (PM2 oneshot drain, XRDP cleanup, pm2-ubuntu.service disable). Documented in 14-02 SUMMARY and pm2-canonical.md.

## Plan Summary

| Plan | Title | Wave | Status | Key result |
|---|---|---|---|---|
| 14-01 | Versionar governor/inviolable e status/install coverage | 1 | ✅ complete | Pre-existing: governor/inviolable units moved to timers.target, status drift report live |
| 14-02 | PM2 boot canonicalization e stale jobs | 2 | ✅ complete (no live mutation) | Repo `pm2-ubuntu.service` rewritten; canonical path documented in `pm2-canonical.md`; 13 PM2 apps preserved online |
| 14-03 | Boot/login-linger, cgroups e XRDP-safe cleanup | 2 | ✅ complete (read-only) | Linger=yes; cgroup profile consistent; XRDP/SSHD not in watchdog cgroup |
| 14-04 | Runbook, rollback e verificacao pos-boot | 3 | ✅ complete (paperwork) | Post-boot checklist + rollback procedure in `srv1-ops.md`; Obsidian result note created |
| 14-05 | Jenkins + servicos orfaos: remove Docker deps | 4 | ✅ complete | container-jenkins.service active; /var/run/docker.sock + /usr/bin/docker removed; jenkins.atius.com.br live (x-jenkins 2.541.3) |
| 14-06 | Jenkins agent on K3s | 5 | ✅ complete | K8s namespace `jenkins` with Deployment (2/2 Running); JNLP secret in vault; foundation for K8s plugin integration |

## Live system state at phase close

| Component | State |
|---|---|
| `loginctl show-user ubuntu -p Linger` | `Linger=yes` |
| `resource-governor-patcher.service` | active (30 moves, healthy_streak=30, mode=base) |
| `resource-governor-watchdog.service` | active |
| `resource-governor-cgroup-init.service` | active |
| `inviolable-watchdog.timer` | active (last run status=0) |
| `omni-builds.slice` / `omni-interactive.slice` / `omni-transfers.slice` | active, profile consistent |
| `omni-builds` direct cgroup | cpu.max=200%/100%, mem.max=8G, swap.max=1G, io.weight=100 |
| `omni-interactive` direct cgroup | cpu.max=125%/100%, mem.max=6G, swap.max=512M, io.weight=50 |
| `omni-transfers` direct cgroup | cpu.max=100%/100%, mem.max=4G, swap.max=256M, io.weight=25 |
| PM2 daemon | running, 13 apps online (12 ATS + 1 Horistic) |
| ats-pm2.service / horistic-pm2.service | inactive (broken path) but apps online via PM2 daemon |
| pm2-ubuntu.service (system) | enabled, inactive (broken path) — repo version fixed, live update gated |
| default.target | has stuck jobs (waiting) — documented in 14-02 SUMMARY |
| `container-jenkins.service` | active, https://jenkins.atius.com.br live (x-jenkins 2.541.3) |
| K8s namespace `jenkins` | 2/2 jenkins-agent pods Running |
| Critical ports 3015/8050/8015/8199 | all listening |

## Gated follow-ups (deferred to explicit user authorization)

1. **`sudo systemctl disable --now pm2-ubuntu.service`:** the system unit is already inactive; this would just remove the auto-start on next reboot. Recovery via `pm2-runtime` documented in `pm2-canonical.md`.
2. **`systemctl --user reset-failed` on stuck oneshots:** clears the failure flag without restarting anything. Could be done immediately and is safe, but was deferred to keep the user-gate clean.
3. **Re-test reboot path:** should be done during a planned maintenance window, with PM2 snapshot + apps snapshot pre-reboot, and verified post-reboot via the checklist in `srv1-ops.md`.
4. **Jenkins K8s plugin install:** user-side action in Jenkins controller UI. After install, the static Deployment (14-06) can be replaced by dynamic pod templates.

## Files created/modified

### Live (systemd + podman + K8s)
- `/home/ubuntu/.config/systemd/user/container-jenkins.service` (rewritten, no Docker orphans)
- `/home/ubuntu/GitHub/containers/jenkins/podman-compose.yml` (rewritten)
- K8s namespace `jenkins` + ServiceAccount + Secret + ResourceQuota + Deployment `jenkins-agent` (2 replicas)

### Repo
- `.planning/phases/14-resource-governor-pm2-boot-hardening/` — 14-01 through 14-06 PLAN + SUMMARY, phase-level SUMMARY, UAT, VALIDATION
- `modules/srv1-ops/systemd/pm2-ubuntu.service` (new, canonical)
- `modules/k3s-ha-portainer-oci/jenkins/agent-deployment.yaml` (new, K8s manifest)
- `inventory/hosts/atius-srv-1.yaml` (apps section, 7 entries including jenkins + jenkins-agent)
- `cli/omni/fleet.py` (`_program_records` extended to read apps + modules)
- `docs/operations/pm2-canonical.md` (new)
- `docs/operations/srv1-ops.md` (Post-Boot + Rollback sections appended)
- `docs/operations/resource-governor.md` (link to pm2-canonical.md)

### Vault
- `/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-13-gsd-plan-phase-resource-governor-pm2.md` (new)
- `/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-15-jenkins-agent-k3s-secret.md` (new, JNLP secret + recovery)

### Backups (preserved)
- `/home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527` (pre-incident)
- `/home/ubuntu/.logs/resource-governor/pm2-hardening-20260615_085957/` (pre-14-02 snapshot)
- `/home/ubuntu/.config/systemd/user/container-jenkins.service.bak.20260615_082613`
- `/home/ubuntu/GitHub/containers/jenkins/podman-compose.yml.docker-deps-20260615.bak`

## Risks closed

- ✅ Governor services depended on `default.target` (now anchored to `timers.target`, 14-01)
- ✅ Inviolable watchdog relaunched via broken units (now timer-triggered, no Install target, 14-01)
- ✅ Status drift between slice and direct cgroup not visible (now reported, 14-01)
- ✅ PM2 boot path with stale `/home/ubuntu/ecosystem.atius.js` (now canonical in repo, 14-02)
- ✅ Jenkins with /var/run/docker.sock + /usr/bin/docker mounts failing (now 100% Podman, 14-05)
- ✅ Jenkins agent path (M005 extension) (now K8s Deployment live, 14-06)
- ✅ XRDP/SSHD could be caught in watchdog cgroup (verified clean, 14-03)

## Risks remaining (Phase 14 +1 follow-ups)

- ⚠ `pm2-ubuntu.service` (system) still references stale path; live update gated
- ⚠ ats-pm2/horistic-pm2 systemd user oneshots remain inactive; apps online via PM2 daemon
- ⚠ default.target has stuck jobs; drain requires reboot or `systemctl --user cancel`
- ⚠ Jenkins controller doesn't have Kubernetes plugin installed; static agent Deployment is a placeholder until plugin is configured
- ⚠ Cloudflare Access policy not enabled; admin edges use Apache Basic Auth

## M006 closure

Phase 14 closes M006 (SRV-1 Resource Governance + PM2 Hardening). 3/6 milestones complete (M001, M002, M003 ✅). M004 + M005 live implemented. M006 in progress → with Phase 14 done, M006 is "live implemented" (the live fix from 2026-06-13 is now versioned, documented, and validated).

Next milestone (M007) is open. Candidate areas: observability stack (M005 follow-up), OCI snapshot workflow, Cloudflare Access policy, or a new direction.

## References

- [[14-01-SUMMARY]] — versioned governor/inviolable + status drift
- [[14-02-SUMMARY]] — PM2 canonical path (no live mutation)
- [[14-03-SUMMARY]] — cgroup consistency + XRDP cleanup validation
- [[14-04-SUMMARY]] — runbook + rollback + Obsidian result
- [[14-05-SUMMARY]] — Jenkins docker-deps cleanup
- [[14-06-SUMMARY]] — Jenkins agent on K3s
- `docs/operations/pm2-canonical.md` — PM2 boot path source of truth
- `docs/operations/srv1-ops.md` — Post-Boot Verification Checklist + Rollback
- `60-LOGS/2026-06-13-resource-governor-pm2-live-fix` — original live fix (vault)
- `60-LOGS/2026-06-13-gsd-plan-phase-resource-governor-pm2` — phase result note (vault)
- `60-LOGS/2026-06-15-jenkins-agent-k3s-secret` — JNLP secret (vault)
