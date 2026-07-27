---
phase: 62-graph-and-context-recovery
status: planned
nyquist: required
---

# Phase 62 Validation Strategy

## Test layers

1. Unit/fixture tests for every new parser, guard, patcher and state transition.
2. Dry-run against redacted snapshots/live read-only state.
3. Canary mutation only after preflight and explicit gate where required.
4. Readback against an independent surface (SQL, MCP, systemd, remote checksum or semantic query).
5. Rollback rehearsal before broad apply.
6. Phase verification maps every owned requirement to evidence.

## Gates mensuráveis incorporados da revisão assíncrona

- Recalcular todos os denominadores live no início; auditoria e revisão divergiram em contagens.
- Preflight real: `gbrain extract all --source db --dry-run --json` e `gbrain reindex --markdown --dry-run --no-embed`.
- Pós-extract/reindex: `links_extraction_lag < 20%`, graph-signals coverage `> 10%` e entity link coverage `>= 5%`; falha gera BLOCK + análise do denominador, nunca edges artificiais.
- Contextual retrieval: check `contextual_retrieval_coverage=ok`, zero elegível pendente/permanent failure não classificada e readback 5/5.
- Órfãos: medir só depois de extract/reindex/CR; redução diagnóstica `>= 50%` sobre baseline recalculado e menos de 20% de falsos órfãos numa amostra determinística de 20.
- Alvo absoluto `<200 órfãos` rejeitado: pode induzir criação cosmética de edges.

## Stop conditions

- Backup/restore gate not PASS.
- Source HEAD/generation drift.
- Secret detected in output/artifact.
- Unknown/malformed evidence.
- Active/deleted denominator ambiguity.
- Error budget, cost cap or timeout exceeded.
- Rollback unavailable or untested.

## Required phase artifact

Create `62-VERIFICATION.md` with PASS/BLOCK/UNKNOWN per requirement, commands, evidence paths and residual risk. The phase cannot close on summary-only evidence.
