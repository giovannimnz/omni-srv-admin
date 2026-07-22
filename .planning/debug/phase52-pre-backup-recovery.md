---
status: awaiting_human_verify
trigger: "Phase 52 Gate B live transaction stopped at PRE_BACKUP with zero writes; recovery became restore-retryable even though no backup or control-plane mutation existed."
created: 2026-07-22
updated: 2026-07-22
---

# Phase 52 PRE_BACKUP Recovery

## Symptoms

- Expected: the sealed Gate B transaction creates a Raft snapshot and exact control-plane bundle before any installation, then proceeds through isolated restore and seven CAS=0 creates.
- Actual: `execute-live` returned an ambiguous transport result. `status-remote` resolved the transaction to `PRE_BACKUP`, zero writes and ownership `NONE`. The transaction directory contained only `wal.json` and `transaction-evidence.json`; no snapshot, bundle or manifest existed. A restore-only resume then moved to `ROLLBACK_BLOCKED_RETRY_REQUIRED` because it required the nonexistent backup.
- Error messages: coordinator `remote-outcome-ambiguous`; after status, `PRE_BACKUP`; after restore-only resume and status, `ROLLBACK_BLOCKED_RETRY_REQUIRED` with blocker `zero-ack-control-plane-restore-failed`.
- Timeline: first live Gate B attempt on 2026-07-22 after two independent PASS reviews and local seal finalization. The flow had not previously run live.
- Reproduction: run the sealed `execute-live` command with the authorized private config on stdin, then query the emitted transaction ID with `status-remote` and `resume-remote`.

## Current Focus

- outcome_v12: satisfied: all exception-to-stdout/stderr boundaries in the executor and coordinator emit only finite/fixed output tokens; arbitrary `Blocked` content never reaches CLI JSON, while safe allowlisted executor reasons remain useful.
- constraints_v12: preserve V11 WAL behavior and 479-test baseline; no external/live/finalize/stage/commit; use only value-free fixed output tokens and retain PENDING seal semantics.
- done_condition_v12: satisfied: RED proved four leaking stages plus arbitrary valid-looking/newline/path/non-string cases; GREEN sanitizes both entrypoints, static audit finds no raw untrusted exception formatting, three-suite regression is green, and a new PENDING hash is generated.
- hypothesis: confirmed and fixed: V11 secured durable WAL artifacts but not the process output boundary; transaction stages re-raised original caller-controlled `Blocked`, and CLI handlers serialized `str(exc)` to stderr JSON.
- prediction: verified: backup, install, restore-test, and reinstall exposed `opaque-sentinel`; rollback was already safe via fixed `rollback-retry-required`; coordinator exposed every injected arbitrary form before the fix.
- fault_tree:
  - OR state-transition bug: `PRE_BACKUP` is admitted to a generic zero-write restore path without a backup-proof guard.
  - OR evidence-projection bug: a useful sanitized pre-backup failure is overwritten by generic ambiguous/restore-blocked evidence.
  - OR backup-path bug: snapshot output destination or subprocess supervision differs between the live transaction and the validated `/dev/null` capability probe.
  - OR environmental failure: the live backup failed transiently despite the same wrapper/supervisor later succeeding; local-only investigation cannot prove this branch without sanitized persisted evidence.
- test: completed: five stage entrypoint probes plus safe token, valid-looking arbitrary token, newline/path, and non-string reasons across executor/coordinator.
- expecting: satisfied: unsafe content collapses to `operation-blocked` or `gate-blocked`; finite safe executor reasons remain unchanged.
- next_action: parent workflow submits PENDING hash `93e0efdc9154423bac2adaaa397b64fd35836550f879257a0ff2dba123fc7bc9` for independent V12 review; this debug session performs no finalize, live mutation, stage, or commit.
- reasoning_checkpoint_v12:
    hypothesis: "Durable artifact sanitization is insufficient because the executor and coordinator top-level exception handlers serialize caller-controlled exception text directly to stderr."
    confirming_evidence:
      - "Executor main prints Blocked reason via str(exc)."
      - "Coordinator main prints GateBlocked reason via str(exc)."
      - "V11 stage handlers persist safe WAL fallbacks but re-raise the original Blocked for backup/install/restore-test/reinstall."
      - "Rollback passes str(exc) only into _rollback_owned, whose finite policy already normalizes it before durable/output use."
    falsification_test: "The hypothesis is false if entrypoint stderr contains only finite tokens for unsafe Blocked/GateBlocked content before production changes."
    fix_rationale: "Apply the same finite semantic policy at the last output boundary; preserve known safe reasons and collapse every non-member to a fixed allowlisted operation-blocked token."
    blind_spots: "Argparse and uncaught non-Blocked Python exceptions are outside the reviewed application JSON contract; tests must cover every application exception-to-JSON path in both files."
- reasoning_checkpoint_v11:
    hypothesis: "A regex proves syntax only, while WAL blocker safety requires provenance from a finite source-authored vocabulary; direct str(exc) producers bypass even syntactic sanitization."
    confirming_evidence:
      - "Parser RED failed for opaque-sentinel in all four representative statuses."
      - "Direct terminal helper preserved opaque-sentinel."
      - "All five producer-stage RED cases persisted opaque-sentinel instead of their expected fixed token."
      - "Audit found raw str(exc) or untrusted blocker assignments in install, restore/reinstall, rollback soft-delete, and rollback terminal paths."
    falsification_test: "The hypothesis would be false if isolated opaque-sentinel were rejected or any producer persisted the fixed expected token before production changes."
    fix_rationale: "One finite allowlist becomes the shared trust boundary; each producer maps non-members to a fixed stage token before the first durable write, while parser rejects non-members before recovery side effects."
    blind_spots: "Existing tests manually injected fixture-only blocker tokens, so they must use real allowlisted production tokens rather than expanding the allowlist for tests."
- reasoning_checkpoint_v9:
    hypothesis: "Unvalidated durable WAL blocker data crosses into recovery because parser shape validation ignores its value and terminalization preserves it with setdefault."
    confirming_evidence:
      - "All 32 unsafe blocker/status validator cases failed RED by not raising."
      - "The PRE_BACKUP integration case also failed RED before its immutability assertions, proving resume accepted the malicious WAL."
      - "The strict-token acceptance case passed, defining the compatibility boundary to preserve."
    falsification_test: "The hypothesis would be false if any unsafe case were already rejected with wal-blocker-invalid or if PRE_BACKUP resume rejected before terminal mutation."
    fix_rationale: "Parser rejection establishes one universal trust boundary for every WAL consumer; explicit terminal overwrite removes the setdefault preservation primitive without weakening valid fixed tokens."
    blind_spots: "Direct internal calls to the terminal helper bypass parser validation, so the helper also needs defense-in-depth normalization to a fixed fallback."
- reasoning_checkpoint:
    hypothesis: "Missing PRE_BACKUP-specific recovery and missing backup-stage exception persistence cause a pre-mutation failure to be misclassified as restore-required and erase the actionable sanitized blocker."
    confirming_evidence:
      - "`run_transaction` durably writes PRE_BACKUP before calling `create_backups`; BACKUP_PROVED and CONTROL_PLANE_INSTALLING are written only after backup artifacts and isolated restore proof succeed."
      - "`resume_transaction` has no PRE_BACKUP branch and its final fallback calls `_restore_zero_ack_terminal`, whose first side effect is `backend.restore_control_plane`."
      - "`run_transaction` has no catch around create/validate/prove backup; current WAL/evidence therefore retain PRE_BACKUP/generic BLOCKED without the sanitized `raft-snapshot-failed` cause."
    falsification_test: "A current-code regression test would refute the hypothesis if PRE_BACKUP resume already terminates without any backend event and the backup failure already persists PRE_BACKUP plus its blocker in WAL/evidence."
    fix_rationale: "Introduce an exact PRE_BACKUP no-mutation terminal before all generic recovery branches, and persist only the sanitized Blocked reason at the backup boundary; post-BACKUP_PROVED and later paths remain unchanged."
    blind_spots: "The discarded live subprocess stderr/exit detail means local artifacts cannot prove whether the original snapshot failed from permissions, timeout, exit code, or a transient runtime condition; the fix can make a future occurrence diagnosable without exposing secrets."
  tdd_checkpoint:
    test_file: "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py"
    test_name: "test_backup_failure_persists_sanitized_pre_backup_blocker_and_state; test_pre_backup_zero_write_resume_is_explicit_no_mutation_terminal; test_backup_failure_never_persists_arbitrary_blocked_detail"
    status: "green"
    failure_output: "unsafe Blocked detail persisted verbatim instead of fixed pre-backup-failed token"

## Evidence

- timestamp: 2026-07-22; V12 reopened after reviewer rejection: WAL artifacts are sanitized, but re-raised caller-controlled `Blocked` content reaches executor stderr JSON; both executor and coordinator output boundaries require finite-token defense.
- timestamp: 2026-07-22; Graphify remains commit-fresh at HEAD `15fe244` with 10,930 nodes; the V12 CLI-output query returned no nodes, so focused exact-text inspection is required.
- timestamp: 2026-07-22; focused audit found raw exception serialization only at executor main line 2600 and coordinator main line 951. The executor rollback `str(exc)` feeds `_rollback_owned`, whose V11 finite policy sanitizes it; no other exception formatting primitive was found in either file.
- timestamp: 2026-07-22; existing tests expose both modules directly and support exact main-boundary capture with `capsys`; the V11 stage backend pattern can drive backup/install/restore-test/reinstall/rollback through executor main without external or live operations.
- timestamp: 2026-07-22; added test-only V12 probes for all five stages, allowlisted executor output, arbitrary valid-looking token, newline/path detail, and non-string exception arguments in both executor and coordinator; production output behavior is unchanged for RED.
- timestamp: 2026-07-22; governed initial V12 RED returned 11 failures and one pass. Ten failures exactly exposed unsafe output across four stages, three executor arbitrary forms, and three coordinator arbitrary forms. Rollback emitted fixed `rollback-retry-required`, not the WAL blocker token expected by the first test draft; this is safe source-authored output and the test expectation must be corrected before counting RED.
- timestamp: 2026-07-22; corrected governed V12 RED returned exactly `10 failed, 2 passed`, `structural_ok=true`: all unsafe cases leak today; source-authored rollback `rollback-retry-required` and allowlisted `raft-snapshot-failed` already satisfy the desired output contract.
- timestamp: 2026-07-22; minimal production fix compiled and governed V12 GREEN returned `12 passed in 0.34s`, `structural_ok=true`: four previously leaking stages now emit `operation-blocked`, safe rollback and raft reasons are preserved, arbitrary/non-string details collapse, and coordinator emits only `gate-blocked`.
- timestamp: 2026-07-22; both reviewed files were audited end-to-end for exception handlers and print/stderr paths. Executor has one blocked JSON stderr boundary using `_safe_output_reason`; coordinator has one using fixed `GATE_BLOCKED_OUTPUT_REASON`; no other application exception-to-output formatting remains.
- timestamp: 2026-07-22; governed combined V11 plus V12 exact regression returned `55 passed in 0.55s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; final governed Gate B suite returned explicit `192 passed in 14.47s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; final governed supply/capacity suite returned explicit `265 passed in 14.11s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; final governed fleet-backup suite returned explicit `34 passed in 11.25s`, exit 0, and `structural_ok=true`; V12 three-suite total is 491 passes, preserving all prior 479 cases plus 12 output-boundary cases.
- timestamp: 2026-07-22; final Python compile, three JSON parses, `git diff --check`, non-test sensitive-marker scan, raw `str/repr(exception)` scan across both entrypoints, and V11 durable blocker-producer audit all passed with exit 0; exactly two reviewed stderr JSON boundaries remain and both are fixed/finite.
- timestamp: 2026-07-22; governed preflight regeneration returned exit 0 and `structural_ok=true`; seal is PENDING with reviews empty, sealed_at null, checks PASS, network/SSH/live false, and hash `93e0efdc9154423bac2adaaa397b64fd35836550f879257a0ff2dba123fc7bc9`.
- timestamp: 2026-07-22; final post-seal assertions, compile, JSON parse, diff, sensitive scan, and raw exception-output scan passed with exit 0. Graphify remains commit-fresh at HEAD `15fe244`; uncommitted changes require the parent workflow's post-commit refresh.
- timestamp: 2026-07-22; two V10 reviewers rejected hash `a66d08e1f257491ee2ba1f804c17051559d6569a3e0fb19a33c40ece72e1f93c`: regex-valid sensitive markers remain trusted and several producers persist raw `str(exc)`.
- timestamp: 2026-07-22; Graphify is commit-fresh at HEAD but returned no task node; exact audit found raw persistence at rollback soft-delete failure, rollback terminal cause, initial install failure, and restore/reinstall failure, while backup/terminal sanitizers still trusted any regex-valid token.
- timestamp: 2026-07-22; added test-only isolated `opaque-sentinel` coverage across parser and direct terminal helper plus five producer stages: backup, install, exact-restore test, reinstall, and rollback soft-delete. Production code remains unchanged for RED.
- timestamp: 2026-07-22; governed V11 RED returned 10 expected failures and 33 passes with `structural_ok=true`: four parser cases, direct terminal, and all five producer stages reproduced the bypass.
- timestamp: 2026-07-22; shared finite blocker allowlist plus stage-specific producer fallbacks and real production fixture tokens returned governed V11 GREEN `43 passed in 0.63s`, `structural_ok=true`.
- timestamp: 2026-07-22; first governed three-suite V11 regression displayed progress through 75 percent with `structural_ok=true` but omitted the terminal pytest summary and exit code; it is treated as inconclusive and not counted as verification.
- timestamp: 2026-07-22; second combined run captured pytest in a child process but the governed scope ended before the child could emit its buffered output or `PYTEST_EXIT`; isolate each suite to distinguish host/runtime termination from a deterministic test failure.
- timestamp: 2026-07-22; isolated governed Gate B suite returned explicit `180 passed in 15.96s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; isolated governed supply/capacity restore suite returned explicit `265 passed in 13.23s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; isolated governed fleet-backup Phase 52 suite returned explicit `34 passed in 11.79s`, exit 0, and `structural_ok=true`; the three verified suites total 479 passes.
- timestamp: 2026-07-22; Python compile, three JSON parses, `git diff --check`, non-test sensitive-marker scan, legacy-regex symbol scan, and raw `wal["blocker"] = str(...)` scan passed with exit 0; audit confirms dynamic persistence now routes through `_safe_blocker` or `_sanitized_blocker`.
- timestamp: 2026-07-22; all six source-authored literal producers now route through `_fixed_blocker`, which checks the same `SAFE_BLOCKER_TOKENS`; the existing strict-token test proves an allowlisted token passes and `opaque-sentinel` fails closed. Governed exact rerun returned `43 passed in 0.69s`.
- timestamp: 2026-07-22; final hardened governed Gate B suite returned explicit `180 passed in 15.07s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; final hardened governed supply/capacity restore suite returned explicit `265 passed in 14.37s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; the final fleet-backup rerun is legitimately queued in `flock --wait=7200`; a concurrent resource-governor audit owns the builds lock, and the scope contains only the waiting flock process with 1 ms CPU, so there is no pytest hang or escaped workload.
- timestamp: 2026-07-22; after the audit released the lock, the final governed fleet-backup suite returned explicit `34 passed in 11.87s`, exit 0; final hardened three-suite verification totals 479 passes.
- timestamp: 2026-07-22; final compile, JSON parse, diff, legacy-symbol, raw-str, and sensitive-marker checks passed before the combined command stopped on a faulty negative-lookahead audit; its output listed only `_fixed_blocker`, `_safe_blocker`, and `_sanitized_blocker` assignments, confirming a checker false positive rather than unsafe code.
- timestamp: 2026-07-22; corrected non-backtracking all-producer audit returned exit 0; every durable `wal["blocker"]` assignment routes through `_fixed_blocker`, `_safe_blocker`, or `_sanitized_blocker`, all backed by the same finite allowlist.
- timestamp: 2026-07-22; governed preflight regeneration returned exit 0, `structural_ok=true`, checks PASS with 70 fault injections, 7 success writes and 3 CAS-conflict rollbacks; seal remains PENDING with reviews empty, sealed_at null, network/SSH/live false, and hash `7a6a34ae19b4fabaa1a8b4cf279a5a50fc4ad8bb1ff194c658d6c174729a6a6f`.
- timestamp: 2026-07-22; final seal assertions, Python compile, JSON parse, diff check, sensitive-marker scan, and all-producer audit passed with exit 0. Graphify remains commit-fresh at HEAD `15fe244`; the parent must refresh it after the eventual commit because these changes are still uncommitted.

- timestamp: 2026-07-22; reviewer V9 reproduced a second-boundary bypass on hash `605c9794901c0a3b6ea8f5591be26e372d446265dc650f9e5780733071f99072`: `_validate_wal` accepted arbitrary blocker values and the PRE_BACKUP terminal preserved them with `setdefault`.
- timestamp: 2026-07-22; Graphify remains commit-fresh at HEAD `15fe244`; task-specific query returned no nodes, so focused reads identified `_validate_wal` and `_terminate_pre_backup_no_mutation` as the exact producer/consumer boundary.
- timestamp: 2026-07-22; added test-only coverage for 8 unsafe blocker values across 4 representative recovery states, one PRE_BACKUP artifact/backend immutability case, and one strict-token acceptance case; production behavior is not yet changed.
- timestamp: 2026-07-22; governed RED produced 33 expected failures and 1 strict-token pass with `structural_ok=true`; every unsafe type/text was accepted, including the integrated PRE_BACKUP resume case.
- timestamp: 2026-07-22; minimal fix added universal present-blocker validation (`str` plus full regex match) and replaced terminal `setdefault` with explicit validated-token-or-fixed-fallback overwrite.
- timestamp: 2026-07-22; governed exact GREEN returned `34 passed`, `structural_ok=true`; unsafe blockers now fail before artifact/backend mutation and strict tokens remain accepted.
- timestamp: 2026-07-22; governed combined regression returned explicit `436 passed in 27.23s`, `PYTEST_EXIT=0`, and `structural_ok=true`; only the pre-existing swap-pressure doctor warning remained.
- timestamp: 2026-07-22; final focused review added direct helper coverage inside the existing strict-token test: even if internal code bypasses parser validation, terminalization overwrites unsafe blocker detail with the fixed fallback. Test count remains 436.
- timestamp: 2026-07-22; post-hardening exact suite returned `34 passed`; combined governed regression returned explicit `436 passed`, and the direct-helper extension remained within the same test instance/count.
- timestamp: 2026-07-22; Python compile, JSON parse, `git diff --check`, and non-test secret scan passed; the scan returned no matches.
- timestamp: 2026-07-22; preflight regenerated `PENDING`, reviews empty, sealed_at null, checks PASS, network/SSH/live false, with hash `a66d08e1f257491ee2ba1f804c17051559d6569a3e0fb19a33c40ece72e1f93c`.

- timestamp: 2026-07-22; transaction `20260722T163940Z-cf840f4c` reported `PRE_BACKUP`, zero versions, live write false and ownership NONE.
- timestamp: 2026-07-22; remote transaction directory was root-owned mode 0700 and contained only WAL and evidence; snapshot, control-plane bundle and manifest were absent.
- timestamp: 2026-07-22; Vault status reported initialized true, sealed false, storage type raft, version 2.0.3.
- timestamp: 2026-07-22; direct wrapper snapshot capability to `/dev/null` returned code 0 with no output.
- timestamp: 2026-07-22; the exact sealed subprocess supervisor also returned code 0 with zero stdout and stderr for the same `/dev/null` capability test.
- timestamp: 2026-07-22; debugger mandatory references and `gsd-debug` workflow were read before investigation; TDD RED and structured reasoning checkpoint are required before a behavior fix.
- timestamp: 2026-07-22; Graphify status is fresh at HEAD `15fe244` with 10,930 nodes and `commit_stale=false`; the task-specific query returned no nodes, so focused exact-text routing is required.
- timestamp: 2026-07-22; exact-text routing located the suspect state transition in `resume_transaction` around lines 1094-1200 and zero-ACK recovery in `_resume_zero_ack_post_backup` around lines 840-860; existing tests cover post-backup states but no explicit `PRE_BACKUP` no-mutation recovery case.
- timestamp: 2026-07-22; initial combined read confirmed `_restore_zero_ack_terminal` always calls `restore_control_plane`, but output truncation prevents attributing `PRE_BACKUP` admission to the exact resume condition yet.
- timestamp: 2026-07-22; bounded complete reads confirm `resume_transaction` excludes `PRE_BACKUP` from the post-backup set, then falls through unconditionally to `_restore_zero_ack_terminal`; that helper always calls `restore_control_plane` and on failure rewrites state to `ROLLBACK_BLOCKED_RETRY_REQUIRED`.
- timestamp: 2026-07-22; `run_transaction` persists WAL `PRE_BACKUP` plus generic evidence `BLOCKED` before `create_backups`, but has no backup-stage exception handler; `LocalVaultBackend.create_backups` collapses any snapshot supervisor failure or missing/empty destination into `raft-snapshot-failed`, and no sanitized blocker is persisted to WAL/evidence.
- timestamp: 2026-07-22; the snapshot command uses `/usr/local/sbin/atius-vault ... save <root-owned-0700-transaction-dir>/raft.snapshot` under a scrubbed child environment; the same bounded supervisor is used for the later successful capability probe, so local code currently distinguishes primarily the output destination, not process supervision.
- timestamp: 2026-07-22; no repo-managed implementation of `/usr/local/sbin/atius-vault` exists, and current production adapter deliberately collapses subprocess detail to `raft-snapshot-failed`; therefore the exact original snapshot runtime trigger is not reconstructable from local code or retained artifacts. The precise reproducible bug is the state-machine fallthrough and missing sanitized stage persistence.
- timestamp: 2026-07-22; `FakeBackend` records every backup/restore/install/metadata/generate operation and Vault put/delete separately, so it can prove the required no-mutation recovery without network or live state.
- timestamp: 2026-07-22; two test-only regressions were added; production code remains unchanged pending proof that both cases fail for the expected state/persistence reasons.
- timestamp: 2026-07-22; governed RED run (`CPUQuota=80%`, structural_ok=true) failed both exact nodes as predicted: WAL lacked `blocker`, and PRE_BACKUP resume returned generic BLOCKED after taking the restore path instead of the dedicated no-mutation terminal.
- timestamp: 2026-07-22; schema inspection found only two coordinator recovery allowlists/semantic sets and the executor WAL/reconciliation sets need the new terminal; live success validation remains PASS-only and requires no change.
- timestamp: 2026-07-22; minimal behavior patch applied: backup-stage `Blocked` now persists sanitized blocker plus PRE_BACKUP evidence; PRE_BACKUP resume branches to `PRE_BACKUP_NO_MUTATION_TERMINAL` before any backend call; exact contract/executor/coordinator semantics recognize only this new zero-write terminal.
- timestamp: 2026-07-22; governed GREEN rerun passed both exact regression nodes (2 passed, structural_ok=true), proving retained partial artifacts, sanitized blocker/state persistence, no restore/install/PUT/delete on PRE_BACKUP recovery, and idempotent terminal rejection.
- timestamp: 2026-07-22; adjacent governed regression passed 13 selected tests covering contract, BACKUP_PROVED/later zero-ACK restore, restore retry, status reconciliation, and recovery validation; no weakening observed.
- timestamp: 2026-07-22; review found `str(exc)` was incorrectly assumed sanitized merely because its type is `Blocked`; exception messages are caller-controlled and require fixed-token normalization before durable persistence.
- timestamp: 2026-07-22; added a test-only unsafe blocker containing whitespace, newline, and secret sentinel; production sanitizer remains unchanged for the RED run.
- timestamp: 2026-07-22; governed sanitizer RED failed exactly as predicted: WAL contained the multiline sentinel-bearing exception text instead of `pre-backup-failed` (1 failed, structural_ok=true).
- timestamp: 2026-07-22; added `_sanitized_blocker` with exact `^[a-z0-9][a-z0-9-]{0,127}$` policy and fixed fallback only at the backup-stage durable persistence boundary.
- timestamp: 2026-07-22; governed three-node GREEN passed (3 passed, structural_ok=true): approved blocker token retained, unsafe detail absent from every transaction artifact, and PRE_BACKUP no-mutation terminal behavior preserved.
- timestamp: 2026-07-22; full Gate B suite produced 136 passes and one failure solely because tracked `gate-b-transaction.json` still records the real live incident as `ROLLBACK_BLOCKED_RETRY_REQUIRED` while its repository invariant test expects the initial redacted `BLOCKED` projection; no code/test regression failed.
- timestamp: 2026-07-22; inspected live incident evidence is value-free and records transaction `20260722T163940Z-cf840f4c`, status ROLLBACK_BLOCKED_RETRY_REQUIRED, write_count 0, ownership NONE, and no network/Windows mutation; these facts are retained here before canonical fixture regeneration.
- timestamp: 2026-07-22; restored tracked runtime evidence exactly to HEAD's canonical initial BLOCKED/pre-live-seal-pending projection via `apply_patch`; no live state was changed.
- timestamp: 2026-07-22; complete Gate B rerun exited without a displayed failure, but the tool output ended at progress dots and omitted the pytest summary; this is not counted as verified until the combined run returns an explicit summary.
- timestamp: 2026-07-22; combined governed Phase 52 regression returned explicit exit 0 and `402 passed in 30.29s`; structural_ok=true, with only pre-existing swap/audit health warnings outside the build containment invariant.
- timestamp: 2026-07-22; static verification passed: both Python tools compile, all three JSON artifacts parse, `git diff --check` is clean, and the non-test Gate B source/evidence scan found no private-key block, bearer-like value, forbidden value field, or test sentinel.
- timestamp: 2026-07-22; governed preflight regenerated status PENDING with reviews=[], sealed_at=null, checks PASS (70 fault injections, success_write_count 7, CAS rollback count 3), and network/SSH/live writes all false; new hash_set_sha256 is `605c9794901c0a3b6ea8f5591be26e372d446265dc650f9e5780733071f99072`.
- timestamp: 2026-07-22; focused status shows exactly five Gate B tracked files modified (contract, executor, coordinator, tests, preflight seal) plus this untracked debug journal; runtime evidence is back to HEAD and unchanged. Graphify reports commit-fresh at HEAD `15fe244`, but uncommitted worktree changes require the parent workflow's post-commit refresh.
- timestamp: 2026-07-22; final focused diff review found contract, executor, and coordinator state semantics symmetric for `PRE_BACKUP_NO_MUTATION_TERMINAL`; PASS/live execution validation is unchanged, and BACKUP_PROVED/later restore behavior remains isolated in its original branches.

## Eliminated

- hypothesis: the transaction created Vault data before failing.
  evidence: status and WAL both show zero writes and ownership NONE.
- hypothesis: the control-plane install ran before failure.
  evidence: WAL remained PRE_BACKUP and the required backup proof that precedes installation never existed.
- hypothesis: Vault was sealed or not using Raft.
  evidence: live status showed sealed false and storage type raft.
- hypothesis: the repository proves the Vault wrapper dropped privileges and could not write the root-owned transaction directory.
  evidence: the wrapper implementation is host-local and absent from managed sources; the later exact supervisor probe succeeds, while the failed run retained neither exit status nor sanitized subprocess category beyond the inferred snapshot stage.

## Resolution

- root_cause: `resume_transaction` had no `PRE_BACKUP` branch, so a zero-write state that precedes backup proof and control-plane installation fell through to `_restore_zero_ack_terminal`; the nonexistent restore proof then manufactured `ROLLBACK_BLOCKED_RETRY_REQUIRED`. Separately, `run_transaction` persisted generic BLOCKED evidence and no sanitized backup-stage blocker, making the exact original snapshot failure unrecoverable from retained local evidence. V9 proved arbitrary blocker values could cross the parser and terminal. V11 proved the regex hardening was syntactic rather than semantic: lowercase `opaque-sentinel` passed it, and stage producers could persist raw exception text. V12 proved artifact safety was still incomplete because both top-level CLI handlers serialized raw exception text to stderr; four stages re-raised caller-controlled content despite their WAL fallback being safe. The only observed runtime delta versus later successful probes is the real root-owned 0700 snapshot destination rather than `/dev/null`; a privilege/path failure is plausible but not proven because the host-local wrapper source and subprocess detail were not retained.
- fix: added exact `PRE_BACKUP_NO_MUTATION_TERMINAL` contract/executor/coordinator semantics; backup-stage failures retain PRE_BACKUP plus a value-free blocker token; PRE_BACKUP resume atomically writes a zero-write ledger/evidence terminal without restore, install, metadata, PUT, or delete and retains partial artifacts. One finite `SAFE_BLOCKER_TOKENS` set is the durable semantic trust boundary. V12 adds a finite `SAFE_OUTPUT_REASONS` projection with argument-safe extraction and `operation-blocked` fallback at executor stderr; coordinator uses fixed `gate-blocked`. Neither reviewed entrypoint formats exception text with `str` or `repr`.
- verification: TDD covered PRE_BACKUP recovery, exception sanitization, parser/terminal rejection, five exception-producing stages, and both CLI output boundaries. V12 RED returned exactly 10 failures and 2 already-safe passes; GREEN returned 12 passes. Combined V11 plus V12 exact coverage returned 55 passes. Final governed suites returned Gate B 192, supply/capacity 265, and fleet-backup 34, totaling 491 passes with exit 0 and `structural_ok=true`. Python compile, three JSON parses, diff check, sensitive-marker scan, raw exception-output scan, and durable producer audit passed. Preflight is PENDING with reviews empty, sealed_at null, checks PASS, no network/SSH/live write, and hash `93e0efdc9154423bac2adaaa397b64fd35836550f879257a0ff2dba123fc7bc9`.
- files_changed: `modules/rustdesk-fleet/contracts/phase52-gate-b-transaction.json`; `modules/rustdesk-fleet/tools/phase52-vault-transaction.py`; `modules/rustdesk-fleet/tools/run-phase52-gate-b.py`; `modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py`; `modules/rustdesk-fleet/evidence/phase52/gate-b-pre-live-verification.json`; `.planning/debug/phase52-pre-backup-recovery.md`.
- residual_risk: the already-transformed live transaction `20260722T163940Z-cf840f4c` is now ROLLBACK_BLOCKED_RETRY_REQUIRED; it cannot be auto-reclassified from WAL alone without weakening legitimate post-backup restore states. No recovery/live mutation was attempted in this debug run.
