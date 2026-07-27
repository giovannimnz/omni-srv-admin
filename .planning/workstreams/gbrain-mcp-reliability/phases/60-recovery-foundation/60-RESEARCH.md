# Phase 60 Research — Recovery Foundation

See `../../RESEARCH.md` for the shared baseline.

## Phase-specific surfaces

Goal: Backups restauráveis, fila serial, secret hygiene e conectividade PgBouncer antes de qualquer mutação de corpus.
Owned requirements: BKP-01, BKP-02, BKP-03, BKP-04, BKP-05, SEC-01, SEC-02, SEC-03, SYNC-01.

The executor must re-read live state before mutation; this research is planning evidence, not live authority. Use repo-managed scripts and tests first. If installed GBrain source must change, require exact version/hash and preserve a byte-identical backup outside Git.
