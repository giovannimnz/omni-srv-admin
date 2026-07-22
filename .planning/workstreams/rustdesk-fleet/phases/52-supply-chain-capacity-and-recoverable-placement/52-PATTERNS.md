# Phase 52: Supply Chain, Capacity and Recoverable Placement - Pattern Map

**Mapped:** 2026-07-20
**Logical files/artifact groups analyzed:** 10
**Close analogs found:** 9 / 10
**Graphify basis:** fresh at `e3bc12b` (`stale=false`, `commit_stale=false`). Exact symbol/file queries routed `validate_phase51.py`, `resource_run`, `restore_drill`, and the backup/offload scripts before focused reads.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `modules/rustdesk-fleet/contracts/supply-chain.json` | config / immutable expectation contract | file-I/O, request-response observations, batch comparison | `modules/rustdesk-fleet/contracts/product-decision.json`; strict contract loading in `validate_phase51.py` | role-match |
| `modules/rustdesk-fleet/contracts/capacity-policy.json` | config / admission policy | file-I/O, integer transform, batch decision | `modules/rustdesk-fleet/contracts/scope.json`; exact-shape validators in `validate_phase51.py` | role-match |
| `modules/rustdesk-fleet/contracts/placement-decision.json` | config / decision model | file-I/O, deterministic state transition | `product-decision.json` plus `derive_product_decision()` | strong role-match |
| `modules/rustdesk-fleet/tools/validate_phase52.py` | validator / live-gate orchestrator / report generator | request-response, remote observation, file-I/O, batch transform | `modules/rustdesk-fleet/tools/validate_phase51.py` | exact role; live extensions required |
| `modules/rustdesk-fleet/tools/rustdesk-vault-hydrate` | security utility / ephemeral provider | stdin/process, tmpfs file-I/O, cleanup event | no conformant in-repo helper; policy references only | no close analog |
| `modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py` | pytest contract/integration test | file-I/O, request-result, subprocess | `modules/rustdesk-fleet/tests/test_phase51_contracts.py` | exact role |
| `modules/rustdesk-fleet/tests/fixtures/{valid,invalid}/...` | positive/negative fixtures | file-I/O, batch mutation | Phase 51 valid bundle and invalid fixture family | exact role |
| `modules/rustdesk-fleet/evidence/phase52/` redacted manifests/results | evidence model / inventory | file-I/O, batch capture | `modules/rustdesk-fleet/evidence/ledger.json`; Phase 51 input manifests | role-match |
| `.../52-GATE-REPORT.json` | generated canonical evidence | batch transform | `.../51-CONTRACT-VALIDATION.json` | exact role |
| `.../52-GATE-REPORT.md` | generated human projection | batch transform | `.../51-CONTRACT-VALIDATION.md` | exact role |

## Pattern Assignments

### Group 1 — Phase 51 contracts and deterministic placement decisions

**Apply to:** `supply-chain.json`, `capacity-policy.json`, and `placement-decision.json`.

**Primary analogs:**

- `modules/rustdesk-fleet/contracts/scope.json:1-86`
- `modules/rustdesk-fleet/contracts/product-decision.json:1-24`
- `modules/rustdesk-fleet/tools/validate_phase51.py:228-267,689-756`

The contract family uses a top-level `schema_version`, typed fields, stable ordered sets, explicit booleans/enums, and no live observation mixed into reviewed policy. The decision contract stores both declared and derived truth, but the validator recomputes the result rather than trusting the stored verdict (`product-decision.json:12-23`; `validate_phase51.py:689-756`).

**Strict loader and repo-path guard** (`validate_phase51.py:228-248`):

```python
def load_json_strict(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key rejected")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)

def validate_repo_path(repo: Path, candidate: Path) -> Path:
    root = repo.resolve()
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError("path is outside repository")
    return resolved
```

Copy the duplicate-key rejection, exact shape/type/enum validation, repo-relative path containment, deterministic ordering, and recomputed verdict pattern.

**Per-contract assignment:**

- `supply-chain.json`: keep reviewed expected tag/commit/digest/checksum/architecture/source fields only. Fresh network resolutions and downloaded-byte hashes belong in redacted evidence, are compared against the contract, and must never rewrite the expected pin automatically.
- `capacity-policy.json`: store integer thresholds and every named non-zero byte reservation from D-04/D-05. The validator must reject booleans-as-integers, floats, negatives, missing/zero defaults, overflow-sized inputs, stale observations, and mismatched filesystem mounts. Percentage gates use `used * 100 <= total * limit`, never `df -h` text or floats. The same contract records D-06 `remediation_policy=none` for `atius-srv-2` and `atius-srv-3`, plus an exact allowlist for bounded isolated reversible full-gate writes only after capacity PASS.
- `placement-decision.json`: derive exactly four outcomes: selected `atius-srv-2`, selected `atius-srv-3` after persisted srv-2 `NO-GO`, selected `horistic-srv` only after both Atius candidates `NO-GO`, or `BLOCKED/no-primary`. A Horistic selection requires `client_colocation=true` and explicit Phase 53/54/57 replan flags. A stored `selected_candidate` must agree with the derived chain.

**Landmines:** contracts are reviewed expectations, not runtime reports; never embed current capacity snapshots, secret values, backup bytes that do not yet exist, or an automatically accepted new upstream digest. Preserve the existing Phase 48/workstream isolation fields rather than introducing a second shared-writer model.

### Group 2 — Phase 51 validator, reports, tests, and Phase 48 isolation

**Apply to:** `validate_phase52.py`, the Phase 52 pytest/fixtures, redacted evidence, and both gate reports.

**Primary analogs:**

- `modules/rustdesk-fleet/tools/validate_phase51.py:213-258,909-971,1034-1070,1239-1355,1378-1474`
- `modules/rustdesk-fleet/tests/test_phase51_contracts.py:144-176,497-540,578-606,696-713`
- `.planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-CONTRACT-VALIDATION.{json,md}`
- `modules/rustdesk-fleet/contracts/scope.json:68-84`

**Stable result/status pattern** (`validate_phase51.py:213-258,1239-1248`):

```python
@dataclass(frozen=True)
class Finding:
    category: str
    path: str
    location: str

@dataclass
class CheckResult:
    id: str
    status: str
    evidence_ids: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

def derive_overall_status(results: list[CheckResult]) -> str:
    if any(item.status == "FAIL" for item in results):
        return "FAIL"
    if any(item.status == "BLOCKED" for item in results):
        return "BLOCKED"
    return "PASS"

def exit_code_for_status(status: str) -> int:
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[status]
```

Phase 52 should keep stable ordered IDs for the four independent requirement gates and any subchecks, collect all findings without disclosing matched material, and preserve `FAIL > BLOCKED > PASS` with distinct exit codes.

**Fresh-input and single-object report pattern** (`validate_phase51.py:1034-1070,1297-1355`): hash each repo input as raw bytes, sort input rows by path, validate currentness against those hashes, build one in-memory report object, and derive `secret_material_present` from finding categories. The JSON report is canonical; Markdown is rendered from the same object.

**Atomic parity outputs** (`validate_phase51.py:1378-1452`):

```python
payloads = (
    (resolved_json, json.dumps(report, indent=2, sort_keys=True) + "\n"),
    (resolved_markdown, render_markdown(report)),
)
for target, content in payloads:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=target.parent,
        prefix=f".{target.name}.", delete=False,
    ) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
for temporary, (target, _) in zip(temporary_paths, payloads, strict=True):
    os.replace(temporary, target)
```

Retain fixed Phase 52 report names, require JSON and Markdown output paths together, reject path escape, and return `2` on invalid invocation/currentness/live prerequisite errors (`validate_phase51.py:1455-1474`).

**Testing pattern:** import the validator as a module, use `tmp_path`/`monkeypatch`, mutate disposable payloads, parameterize boundary/negative matrices, and assert both status and finding category. Copy these proven Phase 51 test shapes:

- disposable-copy drift detection without changing the protected source (`test_phase51_contracts.py:144-176`);
- runtime-generated secret sentinels and assertion that findings contain metadata but not the sentinel (`497-520`);
- exact check set, status precedence, and stale input digest (`578-606`);
- JSON/Markdown parity plus atomic writes that leave unrelated validation files unchanged (`696-713`).

**Phase 48/workstream isolation:** keep `serialized-single-writer` and the `P51-WS-001` precheck / `P51-P48-001` postcheck from `scope.json:68-84`. Phase 52 tests may mutate only a `tmp_path` copy of protected Phase 48 files. The validator must expose no auto-rebaseline option, matching `test_phase51_contracts.py:192-194`.

### Group 3 — Serialized backup, verify-before-delete, and disposable restore drill

**Apply to:** the live backup/restore portion of `validate_phase52.py` and redacted `evidence/phase52/` manifests.

**Primary analogs:**

- `modules/fleet-backup/scripts/rclone-fleet-queue.sh:149-211,236-295`
- `modules/srv1-ops/scripts/offload-dotbackups-to-gdrive.sh:173-231,233-301`
- `cli/omni/oci.py:670-821`
- `cli/omni/tests/test_oci.py:196-265`

**Serialization and bounded remote operation:** `rclone-fleet-queue.sh:149-211` takes a global nonblocking `flock`; `236-295` checks prerequisites, takes a per-host lock, bounds work with `timeout`, and performs a separate verification before declaring success. Phase 52 should use one drill lock per candidate plus bounded timeouts for quiesce, backup A, backup B, restore start, health/integrity checks, and cleanup.

**Verify-before-delete pattern** (`offload-dotbackups-to-gdrive.sh:205-231,256-295`):

```bash
if [ "$local_files" != "$remote_files" ]; then
    return 1
fi
if [ "$local_size" != "$remote_size" ]; then
    return 1
fi
retry_rclone "check:$label" check "$item" "$dest" --one-way --log-level=ERROR

# caller deletes only after copy/archive AND verification succeed;
# otherwise it logs KEEP and returns failure.
```

Copy the control-flow invariant, not the GDrive scope: no source/disposable cleanup occurs until both independently generated archives have verified SHA-256, allowlisted contents/modes, and the selected restore has passed SQLite integrity and public-fingerprint equality. On any failure, retain the source and verified backups and emit `BLOCKED`.

**Disposable restore lifecycle:** `oci.py:735-808` resolves a concrete snapshot identifier, refuses a placeholder for live restore, creates a uniquely named drill target, defaults to cleanup, and records a structured drill log. `test_oci.py:196-265` proves placeholder rejection and structured dry-run capture. Phase 52 should copy those lifecycle ideas while strengthening acceptance to a fresh directory/runtime, pinned ARM64 digest, no published/public network, `PRAGMA integrity_check == ok`, exact public fingerprint equality, stopped/disabled proof, and unchanged legacy access paths.

**Do not copy these weaknesses:**

- `rclone-fleet-queue.sh:275` tests `$?` after saving `rc`; Phase 52 must test the saved return code explicitly.
- Existing fleet SSH calls omit `-n`; every automated Phase 52 SSH/Vault path must use `ssh -n` or equivalent stdin isolation.
- `offload-dotbackups-to-gdrive.sh:173-183` accepts only non-zero archive/manifest sizes; Phase 52 requires cryptographic hashes plus content/mode/SQLite verification.
- `oci.py:802` sets `status="ok"` even if termination fails. Phase 52 cleanup/rollback is its own blocking check and the restored service must be proved inactive.

### Group 4 — Resource-governor admission and guarded execution

**Apply to:** any CPU-heavy supply acquisition, image load/inspection, broad pytest, hashing/archive work, or remote drill operation initiated by `validate_phase52.py`.

**Primary analogs:**

- `cli/omni/srv1_ops.py:140-210,470-546`
- `modules/srv1-ops/configs/resource-governor.env:49-62`
- `cli/omni/tests/test_resource_governor.py:57-137`

**Canonical guarded command construction** (`srv1_ops.py:484-540`):

```python
pdata = _resource_profile(config, profile)
cmd = [
    "systemd-run", "--user", "--scope", "--collect", "--same-dir",
    f"--slice={pdata['slice']}",
]
for name, value in pdata["props"]:
    cmd.extend(["-p", f"{name}={value}"])
if profile == "builds" and config.get("RG_PROFILE_BUILDS_SERIALIZE", "1") == "1":
    cmd.extend(["/usr/bin/flock", f"--wait={queue_timeout}", str(lock_path)])

_run(["bash", str(SCRIPT_MAP["cgroup-init"])], env=_user_systemd_env())
if admission_rc != 0:
    raise click.ClickException("admission gate recusou o build")
rc = _run(cmd, env=_user_systemd_env(), cwd=Path.cwd())
```

The authoritative build profile is `omni-builds.slice`, `RG_PROFILE_BUILDS_CPU_TOTAL_PCT=20`, serialized by the shared lock (`resource-governor.env:49-62`). Tests assert caller working-directory preservation, lock inclusion, fail-closed doctor admission before `systemd-run`, and the four-vCPU `cpu.max` expectation `80000 100000` (`test_resource_governor.py:57-137`).

For a remote candidate, invoke the candidate's managed wrapper through a bounded `ssh -n ... -- omni srv1-ops resources run builds -- <command>` (or the host-equivalent repo wrapper). Record command class, candidate, wrapper/profile, admission verdict, timeout, and exit code; do not record secret-bearing argv or raw secret-capable output. Read-only lightweight probes need bounded SSH but not artificial build classification. If guarded containment cannot be proved, the live gate is `BLOCKED`.

### Group 5 — Vault reference-only validation and non-disclosing findings

**Apply to:** `rustdesk-vault-hydrate`, Vault checks inside `validate_phase52.py`, backup exclusion rules, and all reports/tests.

**Available partial analogs/policy:**

- `modules/rustdesk-fleet/contracts/secret-roles.json:1-32`
- `modules/rustdesk-fleet/tools/validate_phase51.py:833-963`
- `docs/security/atius-secrets-vaults.md:246-278`
- `AGENTS.md:30-45`

The contract already names only approved paths/fields and recovery roles. `validate_secret_roles()` enforces exact references and cardinality, while `scan_secret_material()` recursively emits only `Finding(category, path, location)` and never retains the matched value (`validate_phase51.py:833-963`). Reuse both boundaries.

**Non-disclosing finding core** (`validate_phase51.py:909-963`):

```python
def scan_secret_material(value: Any, path: str = "contract", location: str = "root") -> list[Finding]:
    findings: list[Finding] = []

    def add(category: str, field_location: str) -> None:
        finding = Finding(category, path, field_location)
        if finding not in findings:
            findings.append(finding)

    # recursive visit validates content classes, but findings retain metadata only
    visit(value, location)
    return findings
```

The repo documentation records stdin JSON for Vault writes and requires Linux SSH wrappers to use `ssh -n` (`atius-secrets-vaults.md:246-254`; `AGENTS.md:42`). Phase 52 must extend this to runtime hydration: `umask 077`, confirmed tmpfs under `/run/user/$UID`, `0700` directory, `0600` files, xtrace disabled, cleanup trap, no value in argv/stdout/logs/environment evidence, and aggregate-only password distinctness.

**No conformant helper exists in-repo.** `modules/fork-sync/projects/codex-acp/runtime/hydrate-gateway-env.sh:4-10` is explicitly not an analog to copy: it uses `eval` and persists a secret-bearing `.env` under the home directory. Phase 52 requires a purpose-built stdin-safe/no-output/tmpfs helper. Tests must generate secret sentinels at runtime and assert absence from stdout, stderr, argv evidence, reports, archives, and git fixtures.

## Shared Patterns

### One fail-closed proof pipeline

1. Load reviewed contracts strictly and hash every normative input.
2. Resolve fresh supply observations and reject any drift without changing the expected contract.
3. Measure exact bytes/inodes twice and derive candidate admission using integer arithmetic plus all reservations.
4. Evaluate candidates serially in the locked order with one complete stage vector per attempt: supply, capacity, Vault, backup A/B, isolated restore, `capacity_finalize`, rollback, topology/security. Persist current `NO-GO` before considering the next and never abort fallback merely because Vault, backup, restore, `capacity_finalize`, or rollback failed.
5. Hydrate Vault material ephemerally and produce metadata/cardinality/fingerprint evidence only for a capacity-admitted candidate; a prior gate failure is recorded as an explicit skipped-by-gate stage, not silently omitted.
6. Create two independently generated verified backups and restore one into a fresh isolated runtime. Before selection, run `capacity_finalize`: capture current raw used1/mount/inodes, reconcile actual materialized bytes against reservations, retain unmaterialized log/state/image terms, require the 80% integer inequality and each actual backup size within its 4 GiB reserve. On failure, safely roll back the disposable drill artifacts, persist full-gate `NO-GO`, and continue fallback. Backup A is local; backup B uses the managed `modules/fleet-backup` GDrive path.
7. D-06 forbids cleanup/remediation/reclamation/pruning/deletion and other destructive storage mutation on both Atius candidates. After capacity PASS it permits only bounded isolated reversible staging/load, state-only backup creation, disposable restore state, evidence writes, and verified removal of those disposable drill artifacts; anything else is blocked before command construction.
8. Render canonical JSON and parity Markdown atomically from the same result object.

Any missing, stale, unverifiable, cleanup-incomplete, secret-bearing, or manually waived prerequisite is `BLOCKED`, never a prose-only PASS.

### Remote command and output hygiene

- Construct commands as argument arrays where Python owns the process; avoid shell interpolation of observations or paths.
- Use `ssh -n`, `BatchMode=yes`, explicit connect/command timeouts, canonical host IDs, and a per-candidate lock.
- Route CPU-heavy commands through the managed `builds` profile and prove admission/containment before execution.
- Capture structured, allowlisted result fields. Never attach raw environment, secret-capable stdout/stderr, public-key bytes, private-key bytes, password hashes, or a shell transcript to evidence.

### Exact currentness and parity

- Store raw byte/inode counters, UTC timestamps, filesystem/mount identity, architecture, command/tool versions, and observation input digests.
- Keep expected policy, live observation, generated evidence, and test fixtures in separate paths.
- JSON is authoritative; Markdown is a projection. Both must show the same ordered checks, verdict, timestamp, source HEAD/input hashes, placement outcome, and `secret_material_present=false`.

### Phase 48 and workstream isolation

- Every GSD lifecycle mutation remains explicitly scoped with `--ws rustdesk-fleet`.
- Shared planning/Graphify writers remain serialized.
- Phase 48 integrity is checked after transitions; it is never rewritten or rebaselined by Phase 52 validation.
- Windows MSI verification/staging may be evidence only. Installation and access claims remain Phase 54.

## No Close Analog Found

| File | Why no close analog exists | Planner source |
|---|---|---|
| `modules/rustdesk-fleet/tools/rustdesk-vault-hydrate` | No in-repo helper combines stdin-safe Vault access, confirmed tmpfs, no-output hydration, restrictive modes, cleanup trap, aggregate-only distinctness, and archive exclusion. Existing `hydrate-gateway-env.sh` persists an env file and is incompatible. | Implement directly from `52-RESEARCH.md` Vault Boundary plus `secret-roles.json` and the AGENTS stdin/secret rules. |

The three Phase 52 contract schemas are new domain models, but they have strong structural/decision analogs in Phase 51; the exact supply, capacity, and placement fields must come from `52-RESEARCH.md`, not be invented from older configs.

## Metadata

**Analog search scope:** `modules/rustdesk-fleet`, the Phase 51 workstream artifacts, `modules/fleet-backup`, `modules/srv1-ops`, `cli/omni/oci.py`, `cli/omni/srv1_ops.py`, their focused tests, and Vault policy documentation.

**Strong analog groups stopped at:** 5, matching the requested routing seams. Broader search stopped after exact validator/test/report patterns and the strongest operational partials converged.

**Constraints preserved:** no runtime mutation, no remote mutation, no secret lookup/value access, no Graphify rebuild, no tests/builds, no commit, no Phase 48 edits, and no file modified beyond this pattern map.
