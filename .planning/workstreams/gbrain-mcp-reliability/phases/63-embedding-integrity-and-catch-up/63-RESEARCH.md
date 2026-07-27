# Phase 63 Research — Embedding Integrity and Catch-up

See `../../RESEARCH.md` for the shared baseline.

## Phase-specific surfaces

Goal: Reconciliar provenance/signatures e completar embeddings 768d com quality gates.
Owned requirements: EMB-01, EMB-02, EMB-03, EMB-04, EMB-05.

The executor must re-read live state before mutation; this research is planning evidence, not live authority. Use repo-managed scripts and tests first. If installed GBrain source must change, require exact version/hash and preserve a byte-identical backup outside Git.
