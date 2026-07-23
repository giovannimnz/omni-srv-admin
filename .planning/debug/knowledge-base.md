# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## phase52-report-regression — immutable report fixture expired against the wall clock
- **Date:** 2026-07-23
- **Error patterns:** overall_status BLOCKED, stored verdict drift, topology READY missing, ledger promotion false, stale observation
- **Root cause:** Static Phase 52 report tests rebuilt committed live-capacity evidence through a real wall-clock freshness check, so the fixture expired after the 3600-second policy window.
- **Fix:** Pin the original observation instant only for the four immutable report test nodes through an external pytest compatibility fixture, preserving every Gate A managed source digest.
- **Files changed:** modules/rustdesk-fleet/tests/conftest.py
---
