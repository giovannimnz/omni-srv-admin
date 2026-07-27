# Phase 64 Research — Control Plane, Schema and PostgreSQL

See `../../RESEARCH.md` for the shared baseline.

## Phase-specific surfaces

Goal: Corrigir skills, schema, config planes, métricas e menor privilégio PostgreSQL.
Owned requirements: CTL-01, CTL-02, CTL-03, CTL-04, CTL-05, CTL-06, OBS-01.

The executor must re-read live state before mutation; this research is planning evidence, not live authority. Use repo-managed scripts and tests first. If installed GBrain source must change, require exact version/hash and preserve a byte-identical backup outside Git.
