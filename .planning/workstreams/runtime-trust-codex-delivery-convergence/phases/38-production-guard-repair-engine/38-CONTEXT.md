# Phase 38: Production Guard Repair Engine - Context

**Gathered:** 2026-06-26
**Status:** Ready for execution
**Mode:** Canonical carry-forward of the guarded repair engine already shipped in the repo

## Boundary

Phase 38 formalizes the existing `repair --dry-run --json` and guarded
`repair --apply` path as the canonical PRG-02 / PRG-03 implementation.

## Goal

Confirm that repair planning remains default dry-run, that apply stays gated by
critical blockers and explicit risk flags, and that forbidden operations remain
blocked.
