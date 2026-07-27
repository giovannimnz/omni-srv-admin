# Phase 61 Research — Source Truth and Sync

See `../../RESEARCH.md` for the shared baseline.

## Phase-specific surfaces

Goal: Restaurar o fluxo vault→GBrain e tornar freshness/automação honestos.
Owned requirements: SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06.

The executor must re-read live state before mutation; this research is planning evidence, not live authority. Use repo-managed scripts and tests first. If installed GBrain source must change, require exact version/hash and preserve a byte-identical backup outside Git.
