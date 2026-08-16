# Local Hermes Skills Catalog

Authoritative host-local catalog entries created during this session:

- Obsidian catalog note: `runbooks/hermes-local-skills-catalog.md`
- GBrain catalog page: `runbooks/hermes-local-skills-catalog`
- Dedicated runbook: `runbooks/hermes-wslinterop-restore.md`
- GBrain runbook: `runbooks/hermes-wslinterop-restore`
- GBrain skill page: `runbooks/hermes-wslinterop-restore-skill`

## Why this file exists

The dedicated WSL interop restore skill now lives inside a broader host-local documentation mesh rather than as an isolated skill. Future updates should keep the catalog, the dedicated runbook, and the dedicated GBrain skill page in sync.

## Update rule

When this skill gains a new diagnostic, workaround, or validation step:

1. patch `SKILL.md`
2. update `runbooks/hermes-wslinterop-restore.md`
3. update `runbooks/hermes-wslinterop-restore` in GBrain
4. if the change affects discoverability, update `runbooks/hermes-local-skills-catalog` too
