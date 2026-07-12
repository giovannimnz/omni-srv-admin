# Phase 48 Router Evidence

**Captured:** 2026-07-12
**Source repo:** `/home/ubuntu/GitHub/containers/router-ai-atius`
**Source HEAD:** `20ae5c76f1a22645e97026c1cd6cb517bbf1bfe7`
**Secret material:** omitted by design

## CPU Profile

- profile_cpu_max: 80000 100000
- profile_limits: pass
- focused_go_suite: pass
- execution: `podman-admin.sh profile-run`, isolated `GOCACHE`, `CGO_ENABLED=0`, `GOMAXPROCS=1`, `GOFLAGS=-p=1`

The first local retry overlapped a separate Bun build and lost shared Go cache
artifacts. It was stopped. The canonical Router-owned run used an isolated cache;
the archived Phase 32 verification records the focused controller/service/relay/
codex suite as PASS under the capped profile.

## Auth Matrix

- internal_invalid: pass
- upstream_401_token_invalidated: pass
- upstream_401_refresh_token_invalidated: pass
- upstream_401_invalid_api_key: pass
- upstream_403: pass
- refresh_success: pass
- regenerate_success: pass
- probe_success: pass
- secret_material_present: false

Router internal authentication remains distinct from Codex upstream OAuth
classification. Sanitized metadata, refresh, regenerate and probe behavior are
covered by the archived Phase 32 plan summaries and verification.

## ASVS L1

- V2: pass
- V3: pass
- V4: pass
- V5: pass
- V6: pass

## Canonical Evidence

- `.planning/milestones/v2.17-phases/32-codex-oauth-lifecycle-and-upstream-auth-diagnostics/32-01-SUMMARY.md`
- `.planning/milestones/v2.17-phases/32-codex-oauth-lifecycle-and-upstream-auth-diagnostics/32-VERIFICATION.md`
- `.planning/milestones/v2.17-MILESTONE-AUDIT.md`
- Router commits `77aede1b4` and `20ae5c76f`

The Router-owned OAuth callback lifecycle is evidence for WAC-01/WAC-02 only.
It is not a substitute for the native Codex login required by WAC-03.
