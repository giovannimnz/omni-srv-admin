---
phase: 53-primary-relay-and-public-edge
plan: 05D2H
type: execute
wave: 13
depends_on: [53-05D2D]
gap_closure: true
execution_owner: 53-05D2H
files_modified:
  - modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
  - modules/rustdesk-fleet/evidence/phase53/edge-probes.json
  - modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json
  - modules/rustdesk-fleet/evidence/phase53/lifecycle.json
  - modules/rustdesk-fleet/evidence/phase53/rollback-drill.json
  - modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json
  - modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Before any new authority observation, the exact seven canonical 05F destinations are inventoried and proven absent."
    - "Every pre-existing regular file is moved to a mode-0700 recoverable quarantine under /var/tmp; its original path, size and SHA-256 are recorded in a mode-0600 atomic manifest."
    - "Symlinks, directories, special files, unexpected paths, hash mismatch, existing conflicting pointer or partial recovery state block without provider/live mutation."
    - "A prepared manifest is persisted before the first move and atomically updated after each exact os.replace, so interruption remains recoverable rather than destructive."
    - "The stable pointer /var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json is written last and binds the completed manifest digest; it is never silently overwritten."
    - "Housekeeping performs no host, OCI, Cloudflare, DNS, Vault, RustDesk runtime, provider or network write and creates no authority/owner/journal artifact."
    - "Only 53-05D2H-SUMMARY.md is committed; quarantine bytes stay outside Git and contain no newly fetched secret."
  artifacts:
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md
      provides: "Value-free recoverable-quarantine receipt and seven-path absent proof."
  key_links:
    - from: /var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json
      to: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md
      via: "exact completed manifest SHA-256, moved count and seven canonical paths"
      pattern: "quarantine_manifest_sha256|canonical_paths_absent"
  prohibitions:
    - "Do not delete, truncate, overwrite, normalize, parse as authority or commit any stale evidence byte."
    - "Do not use globs, broad rm/mv/find targets, unresolved environment paths or repository cleanup commands."
    - "Do not generate an OperationPlan or owner approval in this plan; 05E must collect fresh read-only observation afterward."
---

<objective>
Quarantine the already-present stale 05F outputs through an exact, recoverable, value-free local housekeeping transaction and prove all seven canonical destinations absent before 05E observes authority prestate.

Purpose: make the fail-closed `absent` precondition executable without laundering stale evidence or performing a live/provider write.
Output: recoverable `/var/tmp` manifest/pointer plus a summary-only Git receipt; no authority or infrastructure mutation.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/ROADMAP.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 53-05D2H-01: Inventory and recoverably quarantine exact stale outputs</name>
  <files>modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json, modules/rustdesk-fleet/evidence/phase53/edge-probes.json, modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json, modules/rustdesk-fleet/evidence/phase53/lifecycle.json, modules/rustdesk-fleet/evidence/phase53/rollback-drill.json, modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json, modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json</files>
  <action>
Use one local Python housekeeping transaction over the seven literal repository-relative paths above—never a glob. Resolve each beneath the repository root with `lstat`; accept only absent or regular non-symlink files. Compute size/SHA-256 for every existing file and derive a generation ID from the sorted canonical inventory. Create `/var/tmp/omni-rustdesk-phase53-quarantine/<generation-id>` mode 0700 and atomically persist a mode-0600 `manifest.json` with `status=prepared`, exact source/backup mappings, hashes and an initially empty moved set. Refuse an existing generation unless every recorded byte and state matches exactly.

Move each existing file with exact `os.replace` into its generation directory, chmod the backup to 0600, fsync both directories, atomically update/fsync the manifest after each move and re-read the backup hash through `O_NOFOLLOW`. On interruption or mismatch, stop with the manifest showing the exact recoverable partial state; do not proceed to 05E. After all moves, prove every backup hash and all seven original paths lexically absent via `os.path.lexists`, set `status=complete`, then atomically create the stable mode-0600 pointer `/var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json` containing only manifest path, digest and generation ID. If a pointer already exists, accept it only when it binds the exact same completed generation and absent state; otherwise block. Do not inspect payloads beyond byte hashing, contact a provider or create any authority artifact.
  </action>
  <verify>
    <automated>env REPO_ROOT="$(git rev-parse --show-toplevel)" python3 -c 'import hashlib,json,os,re,stat; from pathlib import Path; repo=Path(os.environ["REPO_ROOT"]).resolve(); uid=os.getuid(); rels=["modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json","modules/rustdesk-fleet/evidence/phase53/edge-probes.json","modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json","modules/rustdesk-fleet/evidence/phase53/lifecycle.json","modules/rustdesk-fleet/evidence/phase53/rollback-drill.json","modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json","modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json"]; assert len(rels)==len(set(rels))==7; root=Path("/var/tmp/omni-rustdesk-phase53-quarantine"); rst=root.lstat(); assert stat.S_ISDIR(rst.st_mode) and not root.is_symlink() and rst.st_uid==uid and stat.S_IMODE(rst.st_mode)&amp;0o077==0; pointer=root/"current-phase53.json"; pst=pointer.lstat(); assert stat.S_ISREG(pst.st_mode) and not pointer.is_symlink() and pst.st_uid==uid and stat.S_IMODE(pst.st_mode)&amp;0o077==0; pfd=os.open(pointer,os.O_RDONLY|os.O_NOFOLLOW); praw=os.read(pfd,1048576); os.close(pfd); p=json.loads(praw); assert set(p)=={"manifest_path","manifest_sha256","generation_id"} and re.fullmatch(r"[0-9a-f]{64}",p["generation_id"]); generation=root/p["generation_id"]; gst=generation.lstat(); assert stat.S_ISDIR(gst.st_mode) and not generation.is_symlink() and gst.st_uid==uid and stat.S_IMODE(gst.st_mode)&amp;0o077==0; manifest=Path(p["manifest_path"]); assert manifest.is_absolute() and manifest.parent==generation and manifest.name=="manifest.json"; mst=manifest.lstat(); assert stat.S_ISREG(mst.st_mode) and not manifest.is_symlink() and mst.st_uid==uid and stat.S_IMODE(mst.st_mode)&amp;0o077==0; mfd=os.open(manifest,os.O_RDONLY|os.O_NOFOLLOW); raw=os.read(mfd,8388608); os.close(mfd); assert hashlib.sha256(raw).hexdigest()==p["manifest_sha256"]; doc=json.loads(raw); assert doc["status"]=="complete" and doc["generation_id"]==p["generation_id"] and doc["inventory_sha256"]==p["generation_id"]; assert len(doc["canonical_paths"])==len(set(doc["canonical_paths"]))==7 and sorted(doc["canonical_paths"])==sorted(rels); assert all(not os.path.lexists(repo/r) for r in rels); moved=doc["moved_paths"]; rows=doc["files"]; assert len(moved)==len(set(moved))==len(rows); assert set(moved).issubset(rels) and {row["source"] for row in rows}==set(moved) and len({row["source"] for row in rows})==len(rows); backups=[Path(row["backup"]) for row in rows]; assert len(backups)==len(set(backups)); assert all(path.is_absolute() and path.parent==generation for path in backups); assert all(stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink() and path.lstat().st_uid==uid and stat.S_IMODE(path.lstat().st_mode)&amp;0o077==0 for path in backups); assert all(hashlib.sha256(os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),"rb").read()).hexdigest()==row["sha256"] and path.lstat().st_size==row["size"] for path,row in zip(backups,rows))'</automated>
  </verify>
  <done>A completed recoverable manifest binds every moved byte and all seven canonical destinations are absent.</done>
</task>

<task type="auto">
  <name>Task 53-05D2H-02: Commit a value-free summary-only housekeeping receipt</name>
  <files>.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md</files>
  <action>
Create `53-05D2H-SUMMARY.md` with the 05D2D source/summary ancestors, stable pointer path, completed manifest SHA-256, generation ID, moved count, exact seven canonical paths, `canonical_paths_absent=true`, `provider_writes=0`, `live_mutations=0`, rollback instructions that restore only the exact manifest mappings before any 05E authority exists, and the governed verify result. Do not copy stale payload content. Commit exactly this summary with a literal pathspec and prove its commit changes only the summary.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'SUMMARY=.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md; test -f "$SUMMARY"; test "$(git diff-tree --root --no-commit-id --name-only -r HEAD)" = "$SUMMARY"; git merge-base --is-ancestor "$(git log -n1 --format=%H -- .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md)" HEAD; git diff --check'</automated>
  </verify>
  <done>The committed summary proves recoverable local housekeeping and hands an exact absent prestate to a fresh 05E process.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Severity | Mitigation |
|---|---|---|---|
| T53H-LOSS | Integrity/Availability | critical | Prepared per-file manifest, exact os.replace, fsync, post-move hash and recovery mapping. |
| T53H-LAUNDER | Tampering | critical | Payload bytes are never interpreted as current authority and are moved outside canonical paths. |
| T53H-SCOPE | Tampering | high | Seven literal paths, lstat regular-file checks and no globs/broad cleanup. |
| T53H-REPLAY | Repudiation | high | Stable pointer is write-once/CAS and binds completed manifest digest. |
| T53H-SECRET | Information Disclosure | high | Mode 0700/0600, no payload copy to Git/chat/logs and no secret fetch. |
</threat_model>

<success_criteria>
1. Every existing stale canonical byte is hash-bound and recoverable outside Git.
2. All seven canonical 05F destinations are absent before 05E collection.
3. Conflicting, partial, symlinked or unexpected state blocks.
4. No authority, provider, network or infrastructure write occurs.
5. The only Git change made by execution is the summary-only receipt.
</success_criteria>

<output>Create and commit `53-05D2H-SUMMARY.md`, then stop. 05E starts in a new process and collects fresh prestate.</output>
