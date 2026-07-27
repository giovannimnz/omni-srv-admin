---
phase: 65-observability-docs-and-closeout
status: planned
nyquist: required
---

# Phase 65 Validation Strategy

## Test layers

1. Unit/fixture tests for every new parser, guard, patcher and state transition.
2. Dry-run against redacted snapshots/live read-only state.
3. Canary mutation only after preflight and explicit gate where required.
4. Readback against an independent surface (SQL, MCP, systemd, remote checksum or semantic query).
5. Rollback rehearsal before broad apply.
6. Phase verification maps every owned requirement to evidence.

## Gates comprovados da segunda revisão assíncrona

- Métricas de failure são agrupadas por operation, error class e janela antes de definir alert thresholds.
- Os valores históricos 124/24h e 518/7d são baselines de investigação, não SLOs nem thresholds aceitos.
- Disconnect esperado, race e reranker provider/model/parser têm budgets separados; agregá-los mascara causa raiz.
- Alertas precisam provar redaction, cardinalidade limitada, ausência de storm no canary e entrega real ao operador.
- Não criar timers paralelos para sync/extract/reindex/embed; o scheduler único e seu lock continuam governados pela Phase 61.

## Stop conditions

- Backup/restore gate not PASS.
- Source HEAD/generation drift.
- Secret detected in output/artifact.
- Unknown/malformed evidence.
- Active/deleted denominator ambiguity.
- Error budget, cost cap or timeout exceeded.
- Rollback unavailable or untested.

## Required phase artifact

Create `65-VERIFICATION.md` with PASS/BLOCK/UNKNOWN per requirement, commands, evidence paths and residual risk. The phase cannot close on summary-only evidence.
