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

- outcome_v13: satisfied locally: the reproducible live backup failure is traced to the Vault CLI container namespace, and the adapter now bridges the snapshot through private staging before atomic host publication.
- hypothesis_v13: confirmed: `/usr/local/sbin/atius-vault` runs `vault` via `podman exec hashicorp-vault-atius`; therefore the host transaction path passed to `snapshot save` was resolved inside the container and did not exist.
- done_condition_v13: snapshot save uses an unpredictable container temp, `podman cp` into a root-private staging directory, fd-based identity validation, mandatory container cleanup, and fail-if-exists atomic publish; 18 focused tests and the 506-test governed regression pass; independent adversarial review is PASS.
- outcome_v14: satisfied locally: a rejected hash-bound review found that bootstrap `os.execve` bypassed its cleanup `finally`; the bootstrap now supervises the executor and both layers own verified tmpfs cleanup.
- done_condition_v14: child exit 0/2, context-load failure, cleanup failure, and TERM all have executable coverage; the executor unlinks/fsyncs the private rclone file immediately after validation; the complete governed regression is 511 passes.
- outcome_v15: satisfied locally: rejected V14 review proved the supervisor killed only the direct executor; V15 isolates the executor in its own process group and terminates/reaps the entire group on signal and unexpected exit.
- done_condition_v15: TERM and unexpected-exit tests both spawn a grandchild and prove executor plus descendant absent, no tmpfs root remains, and the complete governed regression is 512 passes.
- outcome_v16: satisfied locally: live transaction `20260722T190633Z-0943450c` proved the snapshot bridge and backup artifacts, then exposed that the isolated restore assumed a host `vault` binary absent on srv3.
- done_condition_v16: the proof resolves `/bin/vault` from the already-running container's validated overlay rootfs, passes it explicitly into the isolated net/mount/pid namespace, and never copies or installs the 508 MB binary.
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

- timestamp: 2026-07-22; a second sealed live attempt, transaction `20260722T181735Z-379852e2`, reproduced `PRE_BACKUP` with zero writes and ownership NONE; V12 resume terminated it as `PRE_BACKUP_NO_MUTATION_TERMINAL` without restore or mutation.
- timestamp: 2026-07-22; the second WAL retained the finite blocker `raft-snapshot-failed`; the transaction directory contained only `wal.json`, `ledger.json`, and redacted evidence, with no snapshot, control-plane bundle, or manifest.
- timestamp: 2026-07-22; read-only inspection proved all six Phase 52 control-plane paths absent, zero Phase 52 authorized-key entries, the approved fingerprint present exactly once, and Vault initialized/unsealed on Raft 2.0.3.
- timestamp: 2026-07-22; live wrapper source showed `exec podman exec ... hashicorp-vault-atius vault "$@"`; the host path `/var/backups/atius-vault/phase52/<txid>/raft.snapshot` was therefore interpreted inside the container. This explains both deterministic failures and the successful `/dev/null` probes.
- timestamp: 2026-07-22; V13 snapshot bridge uses a random container temp, private host staging, `O_NOFOLLOW` plus regular/nlink/uid/size validation, mandatory container cleanup, and `os.link(..., follow_symlinks=False)` atomic no-overwrite publication.
- timestamp: 2026-07-22; adversarial review initially blocked the pre-created-final draft for TOCTOU and later blocked unhandled `OSError` setup/cleanup paths; both findings were fixed before seal/live.
- timestamp: 2026-07-22; governed focused V13 verification returned 18 passes; governed complete Gate B, supply/capacity, and fleet-backup regression returned `506 passed in 40.84s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; independent snapshot-bridge re-review returned PASS for seal/live with no remaining concrete blocker.
- timestamp: 2026-07-22; hash-bound reviewer 2 rejected `8fb6f149...`: successful `os.execve` made the bootstrap `finally` unreachable, and `_reviewed_live_context` failures occurred before the executor operation-level cleanup.
- timestamp: 2026-07-22; read-only srv3 audit found no residual `/dev/shm/atius-phase52-reviewed-*` directory from the two prior attempts.
- timestamp: 2026-07-22; V14 replaces exec-replacement with a child supervisor that propagates exit status, handles TERM/INT/HUP, terminates/waits the child, and retries plus verifies root removal. Executor main also owns cleanup across context-load failure.
- timestamp: 2026-07-22; `private/rclone.conf` is now unlinked and both its directory and bundle root are fsynced immediately after double-digest validation and backend in-memory hydration, before any backup or live transaction work.
- timestamp: 2026-07-22; governed lifecycle tests returned 7 passes covering child exit 0/2, context failure, cleanup failure, TERM child termination, no tmpfs residue, static private unlink, and value-free stderr.
- timestamp: 2026-07-22; governed V14 complete regression returned `511 passed in 49.15s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; hash-bound V14 reviewer rejected `f928f0f6...` after reproducing a surviving executor grandchild under bootstrap TERM; the direct-child-only test was insufficient.
- timestamp: 2026-07-22; V15 starts the reviewed executor with `start_new_session=True` and uses `killpg` TERM followed by bounded SIGKILL in both signal unwind and `finally`; the bootstrap remains outside the child process group.
- timestamp: 2026-07-22; the first TERM regression exposed a signal-handler reentrancy deadlock from calling `child.poll/wait` inside the handler. The handler now only signals the group and raises; process polling/reaping occurs in normal `finally` control flow.
- timestamp: 2026-07-22; two failed test runs left only synthetic fixture tmpfs roots and pid files; exact paths were removed and absence rechecked. No real secret values were involved.
- timestamp: 2026-07-22; governed V15 grandchild TERM and unexpected-exit tests returned 2 passes; governed complete regression returned `512 passed in 39.40s`, exit 0, and `structural_ok=true`.
- timestamp: 2026-07-22; two independent hash-bound reviewers recomputed all 25 rows and approved exact hash `4d6f04c3d5aa22844f65439e77b82a5f8295141fb5fbaccd95d4818bda860e62`; the final seal is PASS at `2026-07-22T19:03:16.005915Z`.
- timestamp: 2026-07-22; live transaction `20260722T190633Z-0943450c` stopped at PRE_BACKUP with zero writes/ownership NONE, but retained a valid 150407-byte Raft snapshot, 10240-byte control-plane bundle, and digest manifest; snapshot namespace bridging is therefore proven live.
- timestamp: 2026-07-22; the WAL blocker was the finite fallback `pre-backup-failed`. Live capability probes showed host `vault` absent, container `/bin/vault` present, overlay binary executable on the host, retained snapshot inspect exit 0, and isolated namespace creation exit 0.
- timestamp: 2026-07-22; V16 validates container name/running state, overlay root shape, merged directory owner/type, and Vault binary owner/type/nlink/executable/size before passing `--vault-bin` to the isolated proof.
- timestamp: 2026-07-22; governed V16 focused coverage returned 21 passes. The first complete regression had 517 passes and one expected fixture-only failure because tracked runtime evidence contained the real PRE_BACKUP incident; the incident is recorded here and the canonical redacted fixture was restored.
- timestamp: 2026-07-22; clean V16 regression returned 518 passes; two independent reviewers rehashed all 25 rows and approved exact hash `fd2c4147be6faf02cbde4196212d67c59d3546c84a349e04fa38ee18cb6050c0`; seal finalized PASS at `2026-07-22T19:17:06.902245Z`.
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
- timestamp: 2026-07-22; transaction `20260722T190633Z-0943450c` resumed under the V16 seal and terminalized `PRE_BACKUP_NO_MUTATION_TERMINAL` with zero writes and ownership NONE.
- timestamp: 2026-07-22; new transaction `20260722T191932Z-fe82bbca` stopped in PRE_BACKUP with zero writes and ownership NONE after retaining a valid snapshot, control-plane bundle, and manifest; no live retry was attempted.
- timestamp: 2026-07-22; an exact network/mount/PID-isolated reproduction against the retained snapshot exposed three Vault 2.0.3 compatibility mismatches: required `api_addr`/`cluster_addr` plus an existing Raft directory, the real `raft/vault.db` filename, and the force endpoint `/v1/sys/storage/raft/snapshot-force`.
- timestamp: 2026-07-22; after the three compatibility fixes, the retained snapshot completed the isolated restore proof with `status=PASS`, `host_listener=false`, `public_listener=false`, and no port bindings. Vault 2.0 health while Shamir-sealed omits cluster ID/storage type, so the no-op-resistant post proof uses initialized+sealed restart and a changed durable `vault.db` digest.
- timestamp: 2026-07-22; canonical runtime evidence was restored after recording the live state here; the governed complete regression returned `562 passed in 29.54s`, exit 0, with `structural_ok=true` and only the pre-existing audit/swap doctor warnings.
- timestamp: 2026-07-22; two independent reviewers recomputed all 25 rows and approved exact hash `496164cb94f29d06fa4d2e588bc2c8b3b8358848eb83345dea03405f2c68dac7`; seal finalized PASS at `2026-07-22T19:36:27.663783Z`.
- timestamp: 2026-07-22; transaction `20260722T191932Z-fe82bbca` terminalized under the V17 seal with zero writes and ownership NONE; new transaction `20260722T193831Z-ac744308` advanced through backup/isolated restore to `CONTROL_PLANE_INSTALLING`, still with zero writes.
- timestamp: 2026-07-22; status correctly found the WAL but rejected stale PRE_BACKUP evidence; resume attempted the zero-ACK restore and persisted `ROLLBACK_BLOCKED_RETRY_REQUIRED` because the original system legitimately lacked `/etc/atius-vault/profiles`, while restore prevalidation incorrectly required every absent target parent to exist.
- timestamp: 2026-07-22; direct exact-source recovery reproduced `control-plane-target-identity-invalid`; current control-plane targets already matched the original manifest byte-for-byte. V18 allows a missing parent only when its target was originally absent and is still absent, persists an initial-install restore failure as a durable retry state, and accepts only monotonic earlier prewrite evidence.
- timestamp: 2026-07-22; focused V18 regression returned 4 passes; exact recovery against the retained transaction then returned `RESTORE_PASS`, proving the absent-parent fix without Vault data writes.
- timestamp: 2026-07-22; pre-seal review caught the original installer failure: reviewed bundle members are intentionally mode 0600, but `install_control_plane` executed the shell source directly. V19 invokes the reviewed source through fixed `/usr/bin/bash`, maps Popen `OSError` to a finite Blocked token, and persists terminal ledger/evidence after both install and reinstall restore paths.
- timestamp: 2026-07-22; V19 also accepts an earlier zero-write prewrite evidence for a terminal BLOCKED WAL while still rejecting evidence ahead of the WAL. Six focused regressions passed.
- timestamp: 2026-07-22; an exact srv3 diagnostic staged the same managed sources as mode 0600, completed `INSTALL_PASS_RESTORE_PASS`, then proved all six targets plus the mutable state tree exactly match the original manifest; no tmpfs diagnostic/review/key directories remain.
- timestamp: 2026-07-22; reviewer V19 rejected an over-broad BLOCKED reconciliation fallback before seal; it now accepts only zero-write PRE_BACKUP evidence and rejects CONTROL_PLANE_INSTALLED/METADATA evidence ahead of a terminal WAL. Governed complete regression returned `566 passed in 30.77s`.
- timestamp: 2026-07-22; both independent reviewers recomputed all 25 rows and approved exact hash `07f16bee83594b286c8ca38c12f2721c5cfd9720bc1397e7b380ad35c493c9c6`; seal finalized PASS at `2026-07-22T19:58:03.040302Z`.
- timestamp: 2026-07-22; transaction `20260722T193831Z-ac744308` resumed to terminal BLOCKED with restored control plane and zero writes. New transaction `20260722T195941Z-dadee6cb` proved install, restore-test, and reinstall, then rolled back before the first write with ownership NONE.
- timestamp: 2026-07-22; the next exact blocker was KV v2 absence formatting: Vault CLI returns `No value found at kv/metadata/...`, not the caller's logical `kv/...` path. V20 derives and byte-validates the exact KV v2 absence path; all seven approved paths then proved pristine live.
- timestamp: 2026-07-22; the pinned OCI archive was transferred and rehashed on srv3, but OCI and docker archive reloads changed/rejected the original registry manifest digest. A governor-capped pull by the immutable ARM64 digest installed the only acceptable runtime image; inspect now includes exact RepoDigest `sha256:17c342...c208`.
- timestamp: 2026-07-22; the classic server image has no `rustdesk-utils`. Exact hbbs keygen proved native files are 64-byte private plus 32-byte public with the public half embedded in the private material. V20 uses an ephemeral `hbbs` container with network none, no ports, read-only root, all caps dropped, no-new-privileges, CPU 0.8, bounded polling, pair validation, and mandatory container/tmpfs cleanup.
- timestamp: 2026-07-22; exact live generation returned `GENERATION_PASS 7 8` without outputting values; no keygen containers or key directories remain. Two empty diagnostic dirs from earlier failed probes were removed; the local transient docker-archive directory was also removed. Remote pinned archives were retained under the approved no-cleanup policy.
- timestamp: 2026-07-22; first V20 review rejected hash `e21550eaf8aa3ad066a2b7646fb5a6425993526f041912979c0edc7d69e1bdea`: an ambiguous `podman create` side effect could precede the local `container_created` flag, and name generation occurred after the key directory was created.
- timestamp: 2026-07-22; V20 now generates the random container name before creating filesystem state, marks the create attempt before spawning, and always issues idempotent `podman rm -f --ignore --time 1` after an attempted create. A fault test simulates create-side-effect plus supervisor timeout and proves both container cleanup dispatch and absent key directory.
- timestamp: 2026-07-22; focused V20 regression returned 4 passes; the complete governed RustDesk suite returned `569 passed in 30.36s`, exit 0, with `structural_ok=true` and only the pre-existing swap-pressure warning.
- timestamp: 2026-07-22; both independent reviewers recomputed all 25 rows and approved exact hash `0004136addd11177d90f240f33cdf1fb9100d4282803d2a501052c7cae5b5617`; seal finalized PASS at `2026-07-22T20:26:48.623213Z` with network/SSH/live-write flags false.

## Eliminated

- hypothesis: the transaction created Vault data before failing.
  evidence: status and WAL both show zero writes and ownership NONE.
- hypothesis: the control-plane install ran before failure.
  evidence: WAL remained PRE_BACKUP and the required backup proof that precedes installation never existed.
- hypothesis: Vault was sealed or not using Raft.
  evidence: live status showed sealed false and storage type raft.
- hypothesis: the Vault wrapper dropped privileges and could not write the root-owned transaction directory.
  evidence: disproved by live wrapper inspection. The wrapper runs as root but executes the Vault CLI inside `hashicorp-vault-atius`; the failure is namespace visibility, not dropped privileges.

## Resolution

- root_cause: the production wrapper runs the Vault CLI inside `hashicorp-vault-atius`, but `LocalVaultBackend.create_backups` originally passed a host-only snapshot path into the container. After bridging that namespace, the disposable restore still encoded pre-2.0 assumptions: missing explicit API/cluster addresses and Raft directory, `raft.db` instead of `vault.db`, and a query-string endpoint instead of `/snapshot-force`. The earlier recovery bug obscured each PRE_BACKUP failure by sending it through a restore path.
- fix: V9-V12 retain the exact PRE_BACKUP no-mutation terminal and finite blocker/output boundaries. V13-V16 bridge and validate the snapshot across the container namespace, supervise cleanup descendants, and route the validated container Vault binary. V17 aligns the isolated restore with Vault 2.0.3. V18-V19 make absence-preserving restore exact, serialize all retry/terminal evidence, reconcile stale evidence monotonically, and execute reviewed mode-0600 installer sources through fixed `/usr/bin/bash`.
- verification: the V17 retained production snapshot completed the exact isolated restore proof with no host/public listener. V18 retained live restore passed. V19 exact mode-0600 install+restore passed on srv3. V20 live metadata, immutable image, and secret-free generation probes passed; the complete 569-test regression and two-reviewer hash-bound seal are PASS.
- files_changed: `modules/rustdesk-fleet/contracts/phase52-gate-b-transaction.json`; `modules/rustdesk-fleet/tools/phase52-vault-transaction.py`; `modules/rustdesk-fleet/tools/run-phase52-gate-b.py`; `modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py`; `modules/rustdesk-fleet/evidence/phase52/gate-b-pre-live-verification.json`; `.planning/debug/phase52-pre-backup-recovery.md`.
- residual_risk: `20260722T163940Z-cf840f4c` is the only legacy `ROLLBACK_BLOCKED_RETRY_REQUIRED`; all later transactions through `20260722T195941Z-dadee6cb` are zero-write terminals with restored control plane. No Vault data versions exist. V20 is sealed but still requires exactly one live transaction before Gate B can be declared PASS.
