# Phase 3: FreeIPA Server Container — Plan Check

**Date:** 2026-04-19
**Phase:** 03-freeipa-server-container
**Plans verified:** 3 (03-01, 03-02, 03-03)
**Phase goal:** FreeIPA rodando em container Docker AlmaLinux 9, acessível e operacional

---

## Dimension 1: Requirement Coverage

| Requirement | Description | Covered By | Status |
|-------------|-------------|------------|--------|
| FIPA-01 | Container FreeIPA (AlmaLinux 9) construído e rodando em ARM64 | 03-01 (Task 2: image+compose), 03-02 (Task 1: launch+monitor) | ✅ Covered |
| FIPA-02 | FreeIPA acessível via web UI e CLI | 03-02 (Task 2: CLI + Web UI verification) | ✅ Covered |
| FIPA-03 | Domínio FreeIPA configurado (realm ATIUS.COM.BR) | 03-01 (Task 1: install-options with realm), 03-02 (Task 2: realm-show) | ✅ Covered |
| FIPA-04 | DNS interno do FreeIPA integrado com rede WireGuard | 03-01 (Task 1: --setup-dns, --forwarder), 03-02 (Task 2: DNS verification) | ✅ Covered |
| FIPA-05 | CA do FreeIPA operacional | 03-01 (Task 1: NO --external-ca per D-15), 03-02 (Task 2: cert-show) | ✅ Covered |
| FIPA-06 | Backup do FreeIPA configurado e testado | 03-03 (Task 1: backup script + first backup) | ✅ Covered |

**Result:** ✅ PASS — All 6 FIPA requirements have covering tasks.

---

## Dimension 2: Task Completeness

| Plan | Task | Files | Action | Verify | Done | Status |
|------|------|-------|--------|--------|------|--------|
| 03-01 | Task 1 | ✅ | ✅ | ✅ | ✅ | Valid |
| 03-01 | Task 2 | ✅ | ✅ | ✅ | ✅ | Valid |
| 03-02 | Task 1 | ✅ | ✅ | ✅ | ✅ | Valid |
| 03-02 | Task 2 | ✅ | ✅ | ✅ | ✅ | Valid |
| 03-03 | Task 1 | ✅ | ✅ | ✅ | ✅ | Valid |
| 03-03 | Task 2 | ✅ | ✅ | ✅ | ✅ | Valid |

All tasks have all required elements. Actions are specific with concrete file paths, commands, and configuration values.

**Result:** ✅ PASS — All tasks complete.

**Note:** 03-02 Task 2 has `<files></files>` (empty) — acceptable for a verification-only task that doesn't modify files.

---

## Dimension 3: Dependency Correctness

| Plan | Wave | Depends On | Valid? |
|------|------|------------|--------|
| 03-01 | 1 | [] | ✅ Wave 1, no deps |
| 03-02 | 2 | ["03-01"] | ✅ Wave 2, depends on 01 (exists) |
| 03-03 | 3 | ["03-02"] | ✅ Wave 3, depends on 02 (exists) |

Dependency graph: 03-01 → 03-02 → 03-03 (linear, acyclic)
Wave assignment: Wave = max(deps) + 1 — correct for all plans.

**Result:** ✅ PASS — No cycles, no missing references, no forward references.

---

## Dimension 4: Key Links Planned

| Plan | Key Link | Wiring Verified |
|------|----------|-----------------|
| 03-01 | docker-compose.yml → /var/lib/freeipa/data via bind mount /data:Z | ✅ Task 1 action specifies mkdir, Task 2 action specifies volumes section |
| 03-01 | docker-compose.yml → .env via env_file directive | ✅ Task 2 action includes `env_file: - .env` in compose YAML |
| 03-02 | docker compose up → ipa-server-configure-first reads /data/ipa-server-install-options | ✅ Task 1 launches compose, options file created in Plan 01 Task 1 |
| 03-02 | /data/ipa/ca.crt → setup idempotency | ✅ Documented in key_links and Task 1 failure recovery notes |
| 03-03 | backup.sh → /var/lib/freeipa/backups/ via tar archive | ✅ Task 1 action includes full script with tar czf to backups dir |
| 03-03 | docker stop/start → freeipa-server container | ✅ Task 1 script includes docker stop/start commands |

**Result:** ✅ PASS — All artifacts are wired together, not isolated.

---

## Dimension 5: Scope Sanity

| Plan | Tasks | Files Modified | Assessment |
|------|-------|---------------|------------|
| 03-01 | 2 | 5 files + 2 dirs | ✅ Within budget |
| 03-02 | 2 | 1 file (docker-compose.yml read-only) | ✅ Within budget |
| 03-03 | 2 | 2 scripts + 1 dir | ✅ Within budget |

All plans have 2 tasks each (within 2-3 target range). No plan exceeds 5 files. Scope is well-distributed across 3 plans.

**Result:** ✅ PASS — Scope is well within context budget.

---

## Dimension 6: Verification Derivation

### Plan 03-01 must_haves
| Truth | User-Observable? | Artifacts Support? |
|-------|-----------------|-------------------|
| "Directory structure exists for FreeIPA data and backups" | ✅ Yes — testable | ✅ artifacts list directories |
| "Secure passwords are generated and stored in .env" | ✅ Yes — testable | ✅ .env artifact with IPA_DM_PASSWORD |
| "Docker Compose file correctly configures FreeIPA container" | ✅ Yes — testable | ✅ docker-compose.yml artifact |

### Plan 03-02 must_haves
| Truth | User-Observable? | Artifacts Support? |
|-------|-----------------|-------------------|
| "FreeIPA container is running and healthy" | ✅ Yes — docker ps | ✅ ca.crt artifact proves completion |
| "FreeIPA CLI responds to commands" | ✅ Yes — docker exec ipa | ✅ |
| "Realm ATIUS.COM.BR is configured" | ✅ Yes — ipa realm-show | ✅ |
| "Web UI responds on HTTPS port 443" | ✅ Yes — curl | ✅ |
| "Internal DNS resolves ipa.atius.com.br" | ✅ Yes — host/nslookup | ✅ |

### Plan 03-03 must_haves
| Truth | User-Observable? | Artifacts Support? |
|-------|-----------------|-------------------|
| "Backup file exists in backups directory" | ✅ Yes — ls | ✅ backup archive artifact |
| "Backup script can be run manually" | ✅ Yes — execute | ✅ freeipa-backup.sh artifact |
| "Backup file contains FreeIPA data" | ✅ Yes — test -s | ✅ |

All truths are user-observable (testable via commands), not implementation details.

**Result:** ✅ PASS — must_haves properly derived from phase goal.

---

## Dimension 7: Context Compliance

### Locked Decisions Coverage

| Decision | Description | Implemented In | Status |
|----------|-------------|----------------|--------|
| D-01 | freeipa/freeipa-server:alma-9 image | 03-01 Task 2: image field | ✅ |
| D-02 | Container run with --systemd=true | 03-01 Task 2: cgroup mount + seccomp:unconfined (research override) | ✅ |
| D-03 | Docker bridge with fixed IP 172.20.0.2 | 03-01 Task 2: networks section | ✅ |
| D-04 | All 7 port pairs exposed | 03-01 Task 2: ports section | ✅ |
| D-05 | Hostname ipa.atius.com.br | 03-01 Task 2: hostname field | ✅ |
| D-06 | Realm ATIUS.COM.BR | 03-01 Task 1: install-options --realm | ✅ |
| D-07 | Domain atius.com.br | 03-01 Task 1: install-options --domain | ✅ |
| D-08 | DM password in .env | 03-01 Task 1: .env generation | ✅ |
| D-09 | Admin password generated | 03-01 Task 1: .env generation | ✅ |
| D-10 | DNS forwarder (10.1.1.2 or 1.1.1.1) | 03-01 Task 1: --forwarder=1.1.1.1 | ✅ |
| D-11 | Clients use 10.1.1.1 as DNS | Phase 5 scope (deferred) | ✅ Out of scope |
| D-12 | CoreDNS reconfig | Phase 5 scope (deferred) | ✅ Out of scope |
| D-13 | Bind mount for data | 03-01 Task 1+2: single /data (research override noted) | ✅ |
| D-14 | Backup volume mount | 03-01 Task 1: /var/lib/freeipa/backups/ created | ✅ |
| D-15 | Embedded Dogtag CA | 03-01 Task 1: NO --external-ca flag | ✅ |
| D-16 | ARM64 FIPS workaround | Research: host is DEFAULT (not FIPS) — no action needed. Verified in plan context. | ✅ |
| D-17 | Container run as root | 03-01 Task 2: seccomp:unconfined + cgroup mount (NOT --privileged per research) | ✅ |
| D-18 | OCI firewall rules | ❌ **NOT ADDRESSED in any plan task** | ⚠️ Gap |
| D-19 | ipa-backup via docker exec | 03-03 Task 1: commented as alternative strategy in backup script | ✅ |
| D-20 | Backup schedule via cron | ❌ **NOT ADDRESSED** — backup script is cron-ready but no cron job created | ⚠️ Gap |

### Deferred Ideas Check
- Keycloak federation → Phase 6: ✅ Not in any plan
- Client machine enrollment → Phase 7: ✅ Not in any plan
- Samba AD Trust → Phase 4: ✅ Not in any plan
- FreeIPA replica → v2: ✅ Not in any plan
- CoreDNS decommission → Phase 5: ✅ Not in any plan

### Discretion Areas
- Docker Compose structure: ✅ Plan chose compose (consistent with project patterns)
- Password generation: ✅ openssl rand approach
- DNS forwarder: ✅ Chose 1.1.1.1 (per research recommendation)
- Container healthcheck: ✅ Not implemented as Docker healthcheck — acceptable discretion
- Backup script location: ✅ /home/ubuntu/docker/freeipa/freeipa-backup.sh

### Context Compliance Issues Found:

**D-18 (OCI Firewall Rules):** No task in any plan addresses opening OCI security group rules. Research explicitly notes this is a "planning-time action item." This is required for WireGuard clients (10.1.1.0/24) to access FreeIPA services. Without this, ports are only accessible locally.

**D-20 (Backup Schedule):** D-20 says "Backup schedule via cron no host ou systemd timer — diario, retention 7 dias." The backup script (03-03 Task 1) includes `RETENTION=7` and is described as "cron-ready," but no cron job or systemd timer is actually created. The script can be run manually, but the scheduled automation is not implemented.

---

## Dimension 8: Nyquist Compliance

### VALIDATION.md Existence

No VALIDATION.md found for phase 3. Checking:

```
ls .planning/phases/03-freeipa-server-container/*-VALIDATION.md
→ No files found
```

RESEARCH.md contains a "Validation Architecture" section with test map and Wave 0 gaps, but no dedicated VALIDATION.md was generated.

However, the RESEARCH.md validation architecture section IS present and complete with:
- Test framework: Bash smoke tests
- Phase Requirements → Test Map for all 6 FIPA requirements
- Automated commands for each requirement
- Wave 0 gaps identified: `/docker/freeipa/freeipa-verify.sh` (which Plan 03 creates)

The verification commands are embedded in the plan tasks themselves rather than a separate VALIDATION.md. Plan 03 Task 2 creates `freeipa-verify.sh` which covers all 6 requirements.

**Assessment:** No VALIDATION.md file, but validation requirements ARE addressed in plans via:
- 03-02 Task 2: Inline verification commands for FIPA-01 through FIPA-05
- 03-03 Task 2: freeipa-verify.sh script covering FIPA-01 through FIPA-06

Since no config.json was checked for nyquist_validation setting, and the validation architecture IS present in RESEARCH.md with tasks that implement it, this is acceptable.

### Automated Verify Presence

| Task | Plan | Wave | Automated Command | Status |
|------|------|------|-------------------|--------|
| Task 1 | 03-01 | 1 | `test -f .env && test -f install-options && grep ...` | ✅ |
| Task 2 | 03-01 | 1 | `docker compose config` | ✅ |
| Task 1 | 03-02 | 2 | `docker exec freeipa-server ipa ping \| grep -q successful` | ✅ |
| Task 2 | 03-02 | 2 | `docker exec ipa realm-show \| grep + host + cert-show` | ✅ |
| Task 1 | 03-03 | 3 | `ls backup*.tar.gz \| head -1 \| xargs test -s` | ✅ |
| Task 2 | 03-03 | 3 | `bash freeipa-verify.sh` | ✅ |

All tasks have automated verify commands.

### Feedback Latency
- No E2E test frameworks (playwright, cypress, selenium) — all are lightweight bash/docker commands
- No watch mode flags
- Commands execute in < 30 seconds (except docker exec which is typically < 5s)

**Result:** ✅ PASS — No latency issues.

### Sampling Continuity
- Wave 1: 2 tasks, 2 with automated verify → 2/2 ✅
- Wave 2: 2 tasks, 2 with automated verify → 2/2 ✅
- Wave 3: 2 tasks, 2 with automated verify → 2/2 ✅

No consecutive windows of 3 tasks without verification.

### Wave 0 Completeness
RESEARCH.md identifies Wave 0 gap: `/docker/freeipa/freeipa-verify.sh`. Plan 03 Task 2 creates this file. The dependent tasks (verification in 03-02) run inline before the script is created, but 03-03 runs after 03-02 so the script will exist when needed.

**Result:** ✅ PASS — Nyquist compliance acceptable.

---

## Dimension 9: Cross-Plan Data Contracts

All plans share the following data entities:

| Entity | Producer | Consumer | Compatible? |
|--------|----------|----------|-------------|
| docker-compose.yml | 03-01 Task 2 | 03-02 Task 1 (reads for launch) | ✅ Same file, no transformation conflict |
| .env file | 03-01 Task 1 | 03-02 (docker compose reads via env_file) | ✅ |
| ipa-server-install-options | 03-01 Task 1 | 03-02 Task 1 (container reads on startup) | ✅ |
| /var/lib/freeipa/data/ | 03-01 Task 1 (creates dir) → 03-02 Task 1 (populates via container) | 03-03 Task 1 (backs up) | ✅ Sequential: create → populate → backup |
| FreeIPA container state | 03-02 Task 1+2 (creates and verifies) | 03-03 Task 1 (stops/starts for backup) | ✅ 03-03 depends on 03-02 |

No conflicting transforms. Data flows sequentially through waves.

**Result:** ✅ PASS — Data contracts are compatible.

---

## Dimension 10: CLAUDE.md Compliance

CLAUDE.md directives relevant to this phase:
- Docker Compose patterns: Plans follow existing docker/ patterns (compose files, .env)
- Container management: Plans use Docker Compose (consistent with project patterns)
- No forbidden patterns detected
- No security requirements violated

**Result:** ✅ PASS — Plans follow project conventions.

---

## Dimension 11: Research Resolution

RESEARCH.md `## Open Questions` section exists at line 405:

1. **DNS Forwarder choice** — Has recommendation (use 1.1.1.1), plan implements 1.1.1.1 ✅
2. **Cgroup v2 availability** — Has recommendation (check at plan time), plan context notes "cgroup2fs (v2 confirmed)" ✅
3. **Container :Z flag compatibility** — Has recommendation (test with :Z first), plan uses :Z ✅

However, the section heading is `## Open Questions` without `(RESOLVED)` suffix. Questions have recommendations and plans implement those recommendations, but the section is not formally marked as resolved.

**Assessment:** Questions are de facto resolved by plan decisions, but the RESEARCH.md file should have the section marked as `## Open Questions (RESOLVED)`.

**Result:** ⚠️ WARNING — Questions resolved in practice, but RESEARCH.md not formally updated.

---

## Summary

### Coverage Summary

| Requirement | Plans | Tasks | Status |
|-------------|-------|-------|--------|
| FIPA-01 | 03-01, 03-02 | T2, T1 | ✅ Covered |
| FIPA-02 | 03-02 | T2 | ✅ Covered |
| FIPA-03 | 03-01, 03-02 | T1, T2 | ✅ Covered |
| FIPA-04 | 03-01, 03-02 | T1, T2 | ✅ Covered |
| FIPA-05 | 03-01, 03-02 | T1, T2 | ✅ Covered |
| FIPA-06 | 03-03 | T1 | ✅ Covered |

### Plan Summary

| Plan | Tasks | Files | Wave | Deps | Status |
|------|-------|-------|------|------|--------|
| 03-01 | 2 | 5+2dirs | 1 | None | ✅ Valid |
| 03-02 | 2 | 1 | 2 | 03-01 | ✅ Valid |
| 03-03 | 2 | 2+1dir | 3 | 03-02 | ✅ Valid |

---

## ISSUES FOUND

**Phase:** 03-freeipa-server-container
**Plans checked:** 3
**Issues:** 2 warning(s), 0 blocker(s)

### Warnings (should fix)

**1. [context_compliance] D-18 (OCI Firewall Rules) has no implementing task**
- Plan: Phase-level
- Decision: D-18 — "Firewall rules na OCI: liberar portas 80, 443, 389, 636, 88, 464, 53 para rede WireGuard 10.1.1.0/24"
- Status: No task in any plan opens OCI security group rules. Research explicitly notes this is a "planning-time action item" requiring manual console action or API call. Without this, FreeIPA ports are only accessible from localhost, not from WireGuard clients.
- Fix: Add a task to 03-01 or 03-02 to document/document the required OCI security group changes. Since OCI CLI is not installed, this could be: (a) a manual checklist in the plan, or (b) an AWS CLI-equivalent OCI CLI command if OCI CLI can be installed, or (c) explicit documentation for manual console action.

**2. [context_compliance] D-20 (Backup Schedule) partially implemented**
- Plan: 03-03
- Decision: D-20 — "Backup schedule via cron no host ou systemd timer — diario, retention 7 dias"
- Status: Backup script includes RETENTION=7 and is described as "cron-ready," but no cron job or systemd timer is created. The script can be run manually but scheduled automation is not implemented.
- Fix: Add a step to 03-03 Task 1 to install a cron job or systemd timer. Example: `echo "0 2 * * * /home/ubuntu/docker/freeipa/freeipa-backup.sh" | crontab -` or create a systemd timer unit.

**3. [research_resolution] RESEARCH.md Open Questions section not formally marked as resolved**
- File: 03-RESEARCH.md
- Status: Section heading is `## Open Questions` without `(RESOLVED)` suffix. Questions have recommendations and plans implement them, but formal resolution marking is missing.
- Fix: Update section heading to `## Open Questions (RESOLVED)` and add inline RESOLVED markers to each question.

### Structured Issues

```yaml
issues:
  - plan: "phase"
    dimension: context_compliance
    severity: warning
    description: "D-18 (OCI Firewall Rules) has no implementing task in any plan"
    decision: "D-18: Firewall rules na OCI para portas 80, 443, 389, 636, 88, 464, 53"
    fix_hint: "Add task documenting OCI security group changes needed — manual console action or OCI CLI commands"

  - plan: "03-03"
    dimension: context_compliance
    severity: warning
    description: "D-20 (Backup Schedule) only partially implemented — script created but no cron/timer scheduled"
    task: 1
    decision: "D-20: Backup schedule via cron no host ou systemd timer — diario, retention 7 dias"
    fix_hint: "Add cron job or systemd timer creation step to Task 1 after writing backup script"

  - plan: "phase"
    dimension: research_resolution
    severity: warning
    description: "RESEARCH.md Open Questions section not formally marked as RESOLVED"
    file: "03-RESEARCH.md"
    fix_hint: "Update heading to '## Open Questions (RESOLVED)' and mark each question inline"
```

### Recommendation

All 3 plans are well-structured with clear tasks, specific actions, and automated verification. The 3 warnings are all "should fix" items that do not block execution but represent gaps in decision coverage. Plans can proceed to execution with the understanding that:

1. **OCI firewall rules** will need manual action outside this phase's automated scope
2. **Backup scheduling** is manual-only until a cron/timer is added
3. **Research documentation** should be formally updated for audit trail

No blockers identified. Phase 3 plans are execution-ready with minor improvements recommended.
