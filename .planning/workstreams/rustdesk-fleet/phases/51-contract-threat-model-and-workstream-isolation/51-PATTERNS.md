# Phase 51: Contract, Threat Model and Workstream Isolation - Pattern Map

**Mapped:** 2026-07-20
**Logical files/artifact groups analyzed:** 21
**Close analogs found:** 17 / 21
**Graphify basis:** fresh at `e36e47b` (`commit_stale=false`); exact queries executed for `_redact_text`, `_redact`, `_sha256_file`, `test_audit_command_filters_action_and_redacts_sensitive_values` and every repository analog named by `51-RESEARCH.md`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `modules/rustdesk-fleet/contracts/scope.json` | config / governance contract | file-I/O, transform | `modules/managed-apps/configs/programs.json`; `scripts/g18-pro-esm-inventory.py` | role-match |
| `modules/rustdesk-fleet/contracts/product-decision.json` | config / decision model | file-I/O, deterministic state transition | `modules/fleet-control-plane/tools/validate_m004.py` | partial |
| `modules/rustdesk-fleet/contracts/threat-model.json` | security model | file-I/O, transform | Phase 26 `26-SECURITY.md`; `modules/managed-apps/configs/programs.json` | role-match |
| `modules/rustdesk-fleet/contracts/permission-profiles.json` | authorization policy config | file-I/O, exact-set transform | `modules/managed-apps/configs/programs.json` | role-match |
| `modules/rustdesk-fleet/contracts/secret-roles.json` | secret-reference inventory | file-I/O, transform | `cli/omni/fleet.py` redaction boundary | partial |
| `modules/rustdesk-fleet/evidence/ledger.json` | evidence ledger / model | file-I/O, batch validation | `ScenarioResult` and `offline_scenarios()` in `validate_m004.py` | partial |
| `modules/rustdesk-fleet/evidence/phase48-baseline.json` | integrity manifest | file-I/O, batch comparison | `_sha256_file()` in `cli/omni/managed_apps.py` | partial |
| `modules/rustdesk-fleet/tools/validate_phase51.py` | validator utility / report generator | file-I/O, batch transform | `validate_m004.py`; Phase 48 `verify-router-evidence.py`; fleet redaction/hash helpers | composite exact-role |
| `modules/rustdesk-fleet/tests/test_phase51_contracts.py` | pytest contract test | file-I/O, request-result | `modules/fleet-control-plane/tests/test_m004_contract.py` | exact-role |
| `modules/rustdesk-fleet/tests/fixtures/valid/minimal-contracts/` | positive fixture bundle | file-I/O | `test_m004_contract.py` temp-file setup | role-match |
| `.../fixtures/invalid/excluded-host.json` | negative scope fixture | file-I/O | G18 allowlist self-test / M004 wrong-host test | role-match |
| `.../fixtures/invalid/duplicate-secret-ref.json` | negative secret-reference fixture | file-I/O | M004 redaction tests | partial |
| `.../fixtures/invalid/forced-relay-default.json` | negative transport fixture | file-I/O | M004 rejected-plan tests | role-match |
| `.../fixtures/invalid/missing-legacy-tool.json` | negative exact-set fixture | file-I/O | G18 host allowlist test | role-match |
| `.../fixtures/invalid/unscoped-gsd-command.md` | negative command-scope fixture | file-I/O, command classification | `validate_probe_command()` in G18 inventory | role-match |
| `.../fixtures/invalid/phase48-drift.json` | negative integrity fixture | file-I/O, comparison | `_sha256_file()` plus `tmp_path` tests | role-match |
| `.../fixtures/invalid/summary-only-ledger.json` | negative evidence fixture | file-I/O, batch validation | M004 stable scenario IDs | partial |
| `.../51-SECURITY.md` | security governance document | review / evidence | Phase 26 `26-SECURITY.md` | exact-role |
| `.../51-OPERATIONAL-REVIEW.md` | human decision gate | review / approval | Phase 45 `45-REVIEWS.md`; Phase 26 sign-off | partial |
| `.../51-CONTRACT-VALIDATION.json` | generated machine report | batch transform | JSON output in `validate_m004.py` | exact-role |
| `.../51-CONTRACT-VALIDATION.md` | generated human projection | batch transform | text projection in `validate_m004.py` | partial |

## Pattern Assignments

### `modules/rustdesk-fleet/tools/validate_phase51.py` (validator utility, batch file-I/O)

**Primary composite analogs:**

- `modules/fleet-control-plane/tools/validate_m004.py:73-100,458-468,690-720`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/tools/verify-router-evidence.py:33-51`
- `cli/omni/fleet.py:82,983-1010`
- `scripts/sso-secret-hygiene-scan.sh:35-77`
- `cli/omni/managed_apps.py:152-157`

**Stable check/result pattern** (`validate_m004.py:73-100`):

```python
@dataclass
class ScenarioResult:
    id: str
    title: str
    status: str
    scope: str
    evidence: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
```

Copy the stable-ID/result-object idea and the ordered aggregation from `offline_scenarios()` (`validate_m004.py:458-468`). Phase 51 should rename the fields to its report contract (`id`, `status`, `evidence_ids`, redacted finding metadata) and preserve the research-defined order of all 11 `P51-*` checks.

**Deterministic JSON pattern** (`validate_m004.py:690-720`):

```python
payload = {"summary": _summary(results), "results": [asdict(result) for result in results]}
print(json.dumps(payload, indent=2, sort_keys=True))
```

Copy deterministic serialization and a single in-memory report object. Unlike the analog, write canonical JSON first and render Markdown from that same object; never re-parse Markdown to decide the verdict.

**Invocation/exit pattern** (`verify-router-evidence.py:33-51`): validate arguments, return an integer, and finish with `raise SystemExit(main())`. Preserve `2` for invalid invocation, but extend the semantics to the locked Phase 51 contract: `0=PASS`, `1=FAIL`, `2=BLOCKED`.

**Redaction pattern** (`cli/omni/fleet.py:82,983-1010`):

```python
SENSITIVE_KEYS = {"secret_ref", "token", "password", "serial", "license_key"}

def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if key in SENSITIVE_KEYS else _redact(nested)
            for key, nested in value.items()
        }
```

Reuse recursive dict/list traversal and deterministic JSON writes. Do not copy `_redact_text()` as the only scanner: it redacts the entire string merely when a sensitive key word occurs and misses the richer content classes required by Phase 51.

**Non-disclosing scanner pattern** (`scripts/sso-secret-hygiene-scan.sh:62-77`): accumulate `(path, line_number, category)` and print only those metadata. Phase 51 must add JSON-field locations and the research-required pattern families, but must never store or echo the matched content.

**Hash pattern** (`cli/omni/managed_apps.py:152-157`):

```python
def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

Use this unchanged for input digests and current Phase 48 filesystem files. Git blob IDs remain a separate provenance field and must not be presented as SHA-256.

**Command-classification analog** (`scripts/g18-pro-esm-inventory.py:42-60,215-224`): compile forbidden mutation patterns, validate one command at a time, and fail immediately. Phase 51 differs by classifying mutating GSD lifecycle verbs and requiring exact `--ws rustdesk-fleet` on each executable command; one scoped command elsewhere must not mask another unscoped command.

**Landmines:**

- `validate_m004.py:700,720` reports `PASS_WITH_BLOCKED` but exits zero unless `FAIL` exists. Phase 51 must exit `2` whenever a prerequisite/review/currentness check is blocked.
- `verify-router-evidence.py:38-45` is substring-marker validation. Do not use it for structured contracts; strict JSON shape, enum, duplicate-key, exact-set and path validation are mandatory.
- Reject duplicate JSON object keys during parsing (for example via `object_pairs_hook`); the ordinary `json.loads()` patterns in existing code silently keep the last duplicate.
- Resolve all supplied paths under the repo root and reject traversal/symlink escape before reading or writing outputs.
- Validation mode must never auto-rebaseline Phase 48. A future explicit rebaseline path requires serialization, reason and reviewer provenance.

### `modules/rustdesk-fleet/tests/test_phase51_contracts.py` (pytest contract test, file-I/O)

**Analog:** `modules/fleet-control-plane/tests/test_m004_contract.py:1-21,145-195,299-317,341-413`

Use the existing import/bootstrap convention (`REPO = Path(__file__).resolve().parents[...]`), `tmp_path` for isolated files, `monkeypatch` for path substitution, and assertions on parsed JSON plus non-zero exit status.

The closest redaction test is `test_audit_command_filters_action_and_redacts_sensitive_values` (`test_m004_contract.py:145-183`), and the malformed-input test is `test_audit_invalid_json_redacts_raw_sensitive_line` (`186-195`). The allowlisted-plan and rejection matrix at `341-413` demonstrates a positive case followed by pending/unknown/wrong-target negatives.

**Required differences:**

- Generate every secret-like sentinel at runtime inside `tmp_path`; do not copy the static realistic-looking literals from the older tests into Phase 51 source or committed fixtures.
- Parameterize the 11 stable `P51-*` checks so a single omitted check cannot disappear silently.
- Assert both exit code and redacted output. A failure test must also assert the generated report contains category/path/field only and does not contain the runtime sentinel.
- Test strict duplicate JSON keys, wrong types, unknown enum values, path escape, missing/stale input hashes, JSON/Markdown parity and the `BLOCKED -> exit 2` distinction.

### Fixture files

**Shared analogs:** `test_m004_contract.py:299-317,341-413`; G18 allowlist negative self-test at `scripts/g18-pro-esm-inventory.py:853-859`.

| Fixture | Pattern to copy | Phase 51 difference / landmine |
|---|---|---|
| `valid/minimal-contracts/` | Build isolated files and invoke the real validator as in M004 `tmp_path` tests. | Must contain the whole positive contract family, exactly 36 pending ledger rows and nine Phase 48 fixture mappings; “minimal” cannot mean partial. |
| `invalid/excluded-host.json` | Wrong-host rejection matrix (`test_m004_contract.py:376-413`). | The excluded name is legal only in an explicit `excluded`/denylist field; reject it as mutation/evidence target. |
| `invalid/duplicate-secret-ref.json` | Recursive structured validation/redaction. | Store names and duplicate Vault references only, never values or value-derived hashes. |
| `invalid/forced-relay-default.json` | Approved-vs-rejected plan shape. | Assert `force_relay_default=true` is a contract violation even if a fallback reason is otherwise valid. |
| `invalid/missing-legacy-tool.json` | G18 allowlist membership check. | Require exact cardinality/equality, not merely “all supplied values are allowed.” |
| `invalid/unscoped-gsd-command.md` | G18 command mutation classifier. | Keep one executable mutating lifecycle command with no `--ws`; do not let prose or a separate scoped command satisfy it. |
| `invalid/phase48-drift.json` | `tmp_path` file mutation plus streaming SHA-256. | Use a harmless temp copy; never modify the preserved Phase 48 source files. |
| `invalid/summary-only-ledger.json` | Stable scenario/evidence IDs. | A narrative/summary path cannot close a PASS row without current machine-readable evidence and input digest. |

Do not put private-key blocks, token-shaped strings, credentials, command transcripts, screenshot OCR content or realistic high-entropy values in committed fixtures.

### Contract JSON family (config/model, file-I/O)

**Serialization analog:** `modules/managed-apps/configs/programs.json:1-10,35-47` uses a top-level `schema_version`, explicit arrays/objects, stable IDs as object keys, booleans, and human rationale in `notes`. `modules/fleet-control-plane/configs/omni-version-matrix.json:1-14` adds component metadata and an explicit target-host list.

All five contracts should use `schema_version: 1`, deterministic ordering, repo-relative evidence/source references, stable enum/ID values, and no runtime-derived data.

#### `contracts/scope.json`

**Behavior analog:** G18 declares an immutable tuple allowlist and rejects unknown requested hosts (`scripts/g18-pro-esm-inventory.py:27,206-212`).

**Difference:** G18 accepts any valid subset and does not reject duplicates. Phase 51 must require exact ordered sets and cardinalities for included hosts, excluded hosts and preserved legacy tools, reject overlaps/aliases/unknown values, and distinguish denylist declaration from a forbidden mutation target.

#### `contracts/product-decision.json`

**Partial analog:** `_summary()` in `validate_m004.py:690-700` derives an overall state from child states rather than accepting a caller-supplied verdict.

**Difference:** implement the research state machine exactly: any mandatory enterprise control derives `NO-GO/pro`; otherwise explicit single-operator acceptance can derive `GO/oss`; missing review/acceptance derives `BLOCKED`. A typed `decision` field must be checked against, never override, the derived result.

#### `contracts/threat-model.json`

**Analog:** Phase 26 `26-SECURITY.md:18-34` separates trust boundaries from a stable threat register with category, component, disposition, mitigation and status.

**Difference:** use the Phase 51 assets/boundaries, STRIDE severities and versioned ASVS IDs from research. Any unresolved `high` must derive `BLOCKED`; a `medium` row needs owner, compensating control and evidence ID. Do not silently downgrade through prose.

#### `contracts/permission-profiles.json`

**Analog:** `programs.json:35-47` models stable policy IDs with typed `kind`, required values and explanatory notes.

**Difference:** encode an explicit capability matrix for both profiles and exact allow/deny values. Record OSS centralized-enforcement limitations as compensating-control risk; do not label the profiles as centralized RBAC under OSS.

#### `contracts/secret-roles.json`

**Analog:** fleet keeps sensitive fields behind recursive redaction (`cli/omni/fleet.py:82,990-1010`).

**Difference:** the contract contains role/name, Vault path and field names, optional public fingerprints, and recovery authority metadata only. Require five distinct target roles/references and separate server private/public roles. Never retrieve values or attempt password distinctness in Phase 51.

### Evidence JSON family (model/manifest, batch file-I/O)

#### `evidence/ledger.json`

**Partial analog:** `ScenarioResult` plus the ordered `offline_scenarios()` list (`validate_m004.py:73-80,458-468`) gives stable IDs, status and evidence as machine data.

**Required shape:** reserve exactly the 36 canonical requirement IDs with `requirement_id`, `owner_phase`, `acceptance_kind`, `status`, `evidence_ids` and `last_verified_at`. Validate exact equality against canonical requirements, unique rows/evidence IDs, allowed paths, currentness and acceptance-kind semantics.

**Landmine:** there is no close existing requirement ledger in the repo. Do not copy M004's free-form evidence strings or accept summary-only evidence as closure.

#### `evidence/phase48-baseline.json`

**Partial analog:** `_sha256_file()` (`cli/omni/managed_apps.py:152-157`) and equivalent `_sha256()` (`cli/omni/xrdp_abnt2.py:115-120`) provide the streaming filesystem digest.

**Required shape:** exactly nine explicit old-to-new rows, source HEAD, legacy Git path/blob ID, current workstream path/SHA-256, `file_count: 9`, and only the documented transient exclusions.

**Landmines:** no close old-path-to-new-path Git/filesystem bridge exists. Do not infer success from empty `git ls-files`, do not conflate Git blob IDs with SHA-256, do not accept missing/extra rows, and do not auto-accept drift.

### `51-SECURITY.md` (security governance, review/evidence)

**Analog:** `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/26-production-guard-boot-login-protocol/26-SECURITY.md:1-68`.

Copy the frontmatter counters/status, `Trust Boundaries`, `Threat Register`, `Evidence`, `Accepted Risks Log`, `Audit Notes`, `Security Audit Trail`, and `Sign-Off` structure. Retain stable threat IDs and explicit disposition/status columns.

**Required differences:** Phase 51 must include the full asset/boundary inventory, T-01 through T-12, ASVS 5.0.0 mappings, unresolved-high blocking rule, medium-risk ownership, OSS limitation language and evidence IDs. The document is a human explanation/projection; `threat-model.json` is the authoritative machine contract.

**Landmine:** Phase 26's checked sign-off is historical evidence. Do not pre-check Phase 51 review boxes or write `PASS` until the current machine report and accountable operational review exist.

### `51-OPERATIONAL-REVIEW.md` (human gate, approval)

**Closest partial analogs:** Phase 45 `45-REVIEWS.md:1-7,15-25,38-48` for status/reviewer frontmatter and finding-to-resolution rows; Phase 26 `26-SECURITY.md:55-68` for audit trail and explicit sign-off.

Use frontmatter with status/reviewer/timestamp, a decision table, unresolved findings, evidence/source references and explicit sign-off. Record the six enterprise controls, whether each is mandatory, the OSS absence acceptance or Pro selection, permission/transport review, Phase 48 drift/rebaseline decision, source HEAD and report digest.

**Landmines:** no close operational acceptance artifact exists. A generic “converged” review is insufficient. The reviewer must be an accountable human/operator, missing review is `BLOCKED`, and no acceptance may be inferred from the PRD or from a Codex-generated summary.

### Generated `51-CONTRACT-VALIDATION.{json,md}` (reports, batch transform)

**JSON analog:** `validate_m004.py:690-720` creates one payload, serializes with `indent=2, sort_keys=True`, and derives overall status from child results.

**Markdown analog:** `_print_text()` at `validate_m004.py:683-687` projects the same result list for humans.

For `51-CONTRACT-VALIDATION.json`, include exactly the research-defined top-level metadata, sorted input digests, all 11 check objects, `secret_material_present` and derived `overall_status`. For `51-CONTRACT-VALIDATION.md`, render source HEAD, validator version, generated time, every input digest, every check ID/status/evidence ID and the identical overall verdict from the same in-memory object.

**Landmines:** the JSON file is authoritative; Markdown must not be parsed back. Missing operational review, stale/missing inputs or Phase 48 drift produces `BLOCKED`, not a narrative PASS. Neither output may contain matched secret-like content, raw commands/process output or screenshot OCR text.

## Shared Patterns

### Strict, deterministic input and output

- Use Python standard library only.
- Parse every JSON object with duplicate-key detection, then validate exact shape/type/enum/path constraints.
- Serialize with `indent=2`, `sort_keys=True`, a trailing newline and stable check ordering (`cli/omni/fleet.py:1003-1005`; `validate_m004.py:714-719`).
- Hash raw input bytes with streaming SHA-256 before validation/report rendering.

### Fail-closed status propagation

- Stable per-check IDs and result objects follow `validate_m004.py:73-100`.
- Overall precedence is `FAIL` over `BLOCKED` over `PASS`, but exit codes remain distinct (`1`, `2`, `0`).
- Human review/currentness/integrity are prerequisites, not optional annotations.

### Redacted findings

- Traverse structured values recursively (`cli/omni/fleet.py:990-1000`).
- Emit only category/path/line-or-field (`scripts/sso-secret-hygiene-scan.sh:62-77`).
- Never include the matched value in exceptions, reports, fixtures or test assertion messages.

### Exact scope and workstream isolation

- Use immutable canonical sets and reject unknowns as in G18 (`scripts/g18-pro-esm-inventory.py:27,206-212`), then strengthen to exact equality/cardinality/no-overlap.
- Parse executable commands individually; every mutating RustDesk lifecycle command must contain exact `--ws rustdesk-fleet`.
- Treat shared planning/Graphify writers as serialized and verify Phase 48 integrity after lifecycle transitions.

## No Close Analog Found

The following artifacts are genuinely new contracts and should follow `51-RESEARCH.md` plus the component patterns above rather than pretending a direct template exists:

| File | Why no close analog exists |
|---|---|
| `modules/rustdesk-fleet/evidence/ledger.json` | No current repo artifact reserves all canonical requirements with evidence IDs/currentness semantics. |
| `modules/rustdesk-fleet/evidence/phase48-baseline.json` | No current manifest bridges legacy Git blobs to migrated filesystem SHA-256 rows. |
| `51-OPERATIONAL-REVIEW.md` | Existing reviews lack the accountable OSS/Pro business-security gate and BLOCKED semantics. |
| `51-CONTRACT-VALIDATION.md` | Existing text reports are not generated parity projections of a canonical JSON report with input hashes. |

## Metadata

**Analog search scope:** `cli/omni`, `modules/fleet-control-plane`, `modules/managed-apps`, `scripts`, and preserved runtime-trust workstream Phase 26/45/48 artifacts.

**Strong analogs stopped at:** 8 source artifacts across the required roles; additional broad search was intentionally avoided after the repo patterns converged.

**Constraints preserved:** no runtime mutation, no secret lookup/value access, no Graphify rebuild, no tests/builds, no commit, and no files modified beyond this pattern map.
