# Hermes/Codex skills + slash commands fleet sharing study — 2026-07-04

> [!WARNING]
> **Estudo histórico/evidence-only; não use suas listas como inventário atual.**
> A autoridade vigente de distribuição é
> `modules/agent-content-packs/manifest-index.yaml`. Para XRDP ABNT2, use a
> skill canônica `$xrdp-abnt2-fleet`, sua fonte versionada em
> `modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`,
> o módulo `modules/xrdp-abnt2/README.md` e o runbook
> `docs/operations/ubuntu-arm64-xrdp-desktop-standard.md`. Comandos históricos
> com `DISPLAY=:10`, edição direta por `sed`/`tee`/`nano`, `xbindkeys`,
> `dpkg-reconfigure`, `pkill`, restart de `xrdp` ou instalação APT implícita
> não são o fluxo XRDP atual. O estudo abaixo permanece intacto como fotografia
> datada da sincronização Hermes/Codex.

## Context

NotebookLM bridge artifacts were imported from `atius-srv-1` to `GIOVANNI-W11-PC`.

Current source locations on `atius-srv-1`:

- Hermes skills: `/home/ubuntu/.hermes/skills/notebooklm-*`
- Codex skills: `/home/ubuntu/.codex/skills/notebooklm-*`
- Codex slash command refs: `/home/ubuntu/.codex/slash-commands/notebooklm*.md`

Current local targets on `GIOVANNI-W11-PC`:

- Hermes skills: `C:/Users/muniz/AppData/Local/hermes/skills/notebooklm-*`
- Hermes slash-command refs mirror: `C:/Users/muniz/AppData/Local/hermes/slash-commands/notebooklm/*.md`
- Codex skills: `C:/Users/muniz/.codex/skills/notebooklm-*`
- Codex slash commands: `C:/Users/muniz/.codex/slash-commands/notebooklm*.md`
- Sync manifest: `C:/Users/muniz/AppData/Local/hermes/sync-manifests/notebooklm-skills-slash-commands-20260704-035212.json`

Important Hermes limitation: Hermes does not dynamically register arbitrary user slash commands from a `slash-commands/` folder. Hermes-native reusable entrypoints are skills. The imported NotebookLM Hermes skills expose slash-like triggers in their frontmatter, and should be loaded with `/skill notebooklm-...` or by asking for the NotebookLM workflow by name. The copied slash command markdown files are reference material and Codex-native command files.

## What was imported now

Hermes skills imported locally:

- `notebooklm-bridge-auto-login`
- `notebooklm-bridge-camofox-display`
- `notebooklm-bridge-camofox-install`
- `notebooklm-bridge-camofox-refresh`
- `notebooklm-bridge-e2e`
- `notebooklm-bridge-maintenance`
- `notebooklm-bridge-safe-export`
- `notebooklm-bridge-smoke`
- `notebooklm-bridge-status`
- `notebooklm-obsidian-bridge`

Codex slash command refs imported locally:

- `notebooklm-bridge-auto-login.md`
- `notebooklm-bridge-camofox-display.md`
- `notebooklm-bridge-camofox-refresh.md`
- `notebooklm-bridge-e2e.md`
- `notebooklm-bridge-maintenance.md`
- `notebooklm-bridge-safe-export.md`
- `notebooklm-bridge-smoke.md`
- `notebooklm-bridge-status.md`

Post-import adjustment: two Linux-only Hermes skills were changed from `platforms: [linux]` to `platforms: [linux, windows]`, because on Windows they are operator runbooks for remote Linux execution on `atius-srv-1`.

## Recommended automatic sharing model

Use a Git-backed content pack as the source of truth, managed by `omni-srv-admin`, then sync/pull into each runtime.

Recommended repo layout inside `omni-srv-admin`:

```text
modules/agent-content-packs/
  notebooklm/
    hermes/skills/notebooklm-*/SKILL.md
    codex/skills/notebooklm-*/SKILL.md
    codex/slash-commands/notebooklm*.md
    manifest.yaml
    README.md
```

Why this is better than ad-hoc SSH copying:

- versioned diffs and rollback through Git;
- source-of-truth independent from whichever machine last edited a skill;
- can validate before install;
- can distribute to both Hermes and Codex targets;
- supports future packages beyond NotebookLM.

## Sync mechanics

Create one idempotent sync command in `omni-srv-admin`, for example:

```bash
omni agent-content sync --pack notebooklm --target hermes,codex --apply
omni agent-content sync --pack notebooklm --target hermes,codex --dry-run
```

On Windows it should map targets to:

```text
Hermes skills      -> C:/Users/muniz/AppData/Local/hermes/skills
Hermes refs mirror -> C:/Users/muniz/AppData/Local/hermes/slash-commands/notebooklm
Codex skills       -> C:/Users/muniz/.codex/skills
Codex commands     -> C:/Users/muniz/.codex/slash-commands
```

On Linux it should map targets to:

```text
Hermes skills      -> ~/.hermes/skills
Hermes refs mirror -> ~/.hermes/slash-commands/notebooklm
Codex skills       -> ~/.codex/skills
Codex commands     -> ~/.codex/slash-commands
```

The sync should:

1. read `manifest.yaml`;
2. compute source/destination SHA-256 per file;
3. show dry-run diff;
4. back up overwritten destinations to `.bak-agent-content-<timestamp>`;
5. apply only allowlisted paths;
6. validate skill frontmatter starts at byte 0 with `---`, has `name` and `description`;
7. validate no obvious secrets/cookies/tokens/HAR files are included;
8. write a local JSON manifest with hashes and backups;
9. optionally run `hermes skills list` or tell the operator to `/reload-skills`.

## Scheduling options

Preferred automation order:

1. Manual pull first: `omni agent-content sync --pack notebooklm --dry-run`, then `--apply`.
2. Scheduled pull later, once stable:
   - Windows: Scheduled Task running the sync script daily or on logon.
   - Linux: systemd user timer or cron.
3. Avoid bidirectional auto-sync initially. Skills are code-like operational instructions; conflicts need human review.

A safe scheduled mode should be `pull-only` from the Git source of truth to local runtimes. Pushes should remain manual through Git PR/commit.

## Alternative models considered

### SSH tar pull from `atius-srv-1`

This is what was used for the one-time import. It is useful as a bootstrap, but weaker as a permanent model because `atius-srv-1` becomes both runtime and source-of-truth with no review boundary.

### Hermes profile export/import

Too coarse. It copies much more than skills and can move credentials/config/session state accidentally.

### Private Hermes skill tap / skills registry

Good future path for Hermes-only skills. Does not solve Codex slash command markdown unless paired with a Codex content-pack step.

### Obsidian/GBrain as source of truth

Good for documentation and decisions, not ideal as the direct executable artifact source. The executable artifact source should be Git.

## Proposed next implementation phase

1. Add `modules/agent-content-packs/notebooklm/` to `omni-srv-admin`.
2. Move/copy the imported source artifacts into that pack.
3. Implement `scripts/sync-agent-content-pack.py` with `--dry-run` and `--apply`.
4. Add `omni agent-content sync` CLI wrapper.
5. Validate on GIOVANNI-W11-PC and atius-srv-1.
6. Only after two clean manual syncs, add scheduled pull.

## Safety rules

- Never sync secrets, `.env`, cookies, browser profiles, HAR, `storage_state.json`, `BW_SESSION`, or NotebookLM auth state.
- Do not auto-delete destination files unless `manifest.yaml` explicitly marks them owned and the operator passes `--prune`.
- Prefer pull-only automation. Push/manual review keeps skill drift intentional.
- Treat Codex slash commands as Codex-native; in Hermes they are reference files unless Hermes core gains custom user slash-command loading.
