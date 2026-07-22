# Phase 53: Primary Relay and Public Edge - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-22
**Phase:** 53-primary-relay-and-public-edge
**Mode:** `--auto`, authorized by the operator request to plan and execute
**Areas discussed:** colocated server isolation, native edge, external probes, operational API, persistence and rollback

---

## Colocated server isolation

| Option | Description | Selected |
|---|---|---|
| Separate server/client domains | Independent state, service, resource, evidence and rollback scopes | ✓ |
| Shared host-level RustDesk domain | Reuse paths and lifecycle between server and future client | |

**Choice:** Separate server/client domains.
**Notes:** Required by the approved Horistic topology impact review.

## Native edge

| Option | Description | Selected |
|---|---|---|
| DNS-only minimal native ports | Publish only TCP 21115-21117 and UDP 21116 with negative probes | ✓ |
| Broad RustDesk default range | Also expose 21114/21118/21119 | |

**Choice:** DNS-only minimal native ports.
**Notes:** The broader range conflicts with the OSS/product contract.

## External probes

| Option | Description | Selected |
|---|---|---|
| Windows private-first probe plus independent corroboration | Test from outside Horistic and retain redacted TCP/UDP evidence | ✓ |
| Same-host/localhost scan | Validate only local listeners | |

**Choice:** Windows-origin external probe with a second external source when practical.
**Notes:** Localhost success is explicitly insufficient for Phase 53.

## Operational API

| Option | Description | Selected |
|---|---|---|
| Separate authenticated read-only ATIUS API | Versioned health/readiness/status/metrics, redacted and not RustDesk API Server | ✓ |
| Enable native RustDesk API port | Use client API Server/TCP 21114 | |
| No central endpoints | Rely only on service/unit state | |

**Choice:** Separate authenticated read-only ATIUS API.
**Notes:** Preserves the accepted RustDesk OSS boundary while implementing the operator-approved central endpoints.

## Persistence and rollback

| Option | Description | Selected |
|---|---|---|
| Three restarts plus real boot and transactional rollback | Prove identity, data, listeners, limits and fallbacks | ✓ |
| Unit-active smoke only | Skip boot and rollback proof | |

**Choice:** Full restart/boot/rollback gate.
**Notes:** Any loss of identity, listener drift or fallback regression keeps Phase 54 blocked.

## the agent's Discretion

- Operational API implementation language/framework.
- Exact per-process resource split inside the approved aggregate ceilings.
- Secondary external probe provider and redacted evidence schema.

## Deferred Ideas

- Client installation and canary UX/security proofs remain Phases 54-55.
- Full transport matrix and DR remain Phases 56-57.
