# Fork Sync Audit — 2026-06-13

## Result

`fork-sync doctor` passed. Active projects were synced through the new
`sync-all --apply` safety gate. No upstream merge was needed today.

## Commands Run

```bash
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync doctor
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync --json sync atius-router --dry-run
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync --json sync atius-router-docs --dry-run
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync --json sync atius-router
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync --json sync-all
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync --json sync-all --apply
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync --json containers mirrors
PYTHONPATH=modules/fork-sync/cli pytest -q modules/fork-sync/cli/tests/test_sync_runner.py
```

## Controlled Projects

| Project | Status | Result |
|---|---|---|
| `atius-router` | active | Clean, already contains `upstream/main`, ahead by 45, pushed/up-to-date on origin |
| `atius-router-docs` | active | Clean, already up-to-date |
| `aionui` | paused | Local clone tracks upstream only; no safe `giovannimnz` fork origin |
| `bruno` | paused | Local fork path missing |
| `get-shit-done` | paused | Local fork path/repo missing |
| `gsd-2` | paused | Local fork path/repo missing |
| `hermes-backend` | paused | User requested Hermes/Hermes OS paused |
| `hermes-desktop` | paused | User requested Hermes/Hermes OS paused |
| `horus-spec-driven` | paused | Requires custom submodule/installer runner |

## Container Mirrors

`~/GitHub/containers` currently has invalid copied `.git` directories for the
two projects declared in fork-sync:

| Project | Canonical worktree | Container mirror | Result |
|---|---|---|---|
| `atius-router` | `/home/ubuntu/docker/Atius/router-ai-atius` | `/home/ubuntu/GitHub/containers/Atius/router-ai-atius` | mirror `.git` invalid |
| `atius-router-docs` | `/home/ubuntu/GitHub/containers/router-ai-atius/docs/atius-router-docs` | n/a | canonical worktree since 2026-07-05; legacy `containers/Atius` copies quarantined |

Decision: keep `~/docker` as canonical for these two until the mirrors are
recloned or repaired. Do not point fork-sync to the broken mirrors.

## Should-Be-Controlled Candidates

These repos/programs exist locally but are not safe to enroll automatically:

| Path | Reason |
|---|---|
| `/home/ubuntu/GitHub/forks/OfficeCLI` | Clean upstream clone; needs fork ownership decision before sync config |
| `/home/ubuntu/GitHub/Programs/CLI-Anything` | Upstream clone, dirty local change |
| `/home/ubuntu/GitHub/Programs/codex-desktop-linux` | Dirty and diverged 2/2 from origin |
| `/home/ubuntu/GitHub/termux-s23/*` | Clean upstream clones, likely reference/subproject ownership |
| `/home/ubuntu/docker/Atius/ai-apps` | Very dirty live app tree; not safe for automated merge |
| `/home/ubuntu/docker/Outros` | Very dirty mixed tree; not safe for automated merge |
| `/home/ubuntu/docker/Outros/streaming-service` | Clean tracked files but many untracked files; needs ownership decision |

## Automation Added

- `fork-sync sync-all`: dry-run all active projects.
- `fork-sync sync-all --apply`: apply only when dry-run is safe.
- `fork-sync containers mirrors`: report invalid container mirrors before sync path migration.

Safety gates for `sync-all --apply`:

- project enabled and not paused
- dry-run status is success
- `can_apply` is true
- no dirty files
- no unprotected conflicts
- no stale protected paths
