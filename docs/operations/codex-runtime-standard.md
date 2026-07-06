# Codex Fleet Runtime Standard

Canonical Codex runtime standard for the managed machines:

- `C:\Users\muniz\.codex` on `GIOVANNI-W11-PC`
- `/home/ubuntu/.codex` on `atius-srv-1`
- `/home/ubuntu/.codex` on `atius-srv-2`
- `/home/ubuntu/.codex` on `atius-srv-3`
- `/home/horistic/.codex` on `horistic-srv`

## Default config

Keep this in the base `config.toml`:

```toml
model = "gpt-5.4"
model_reasoning_effort = "medium"
model_context_window = 1000000
model_auto_compact_token_limit = 900000
service_tier = "normal"
```

Why this is the default:

- Current Codex local catalog exposes `gpt-5.4` with `max_context_window = 1000000`.
- Current Codex local catalog exposes `gpt-5.5` with `max_context_window = 272000`.
- `gpt-5.4` is the only practical Codex local path for 1M context on this fleet.
- `medium` is the best daily default for latency, throughput, and stability.

## Standard profiles

Create these files next to the base config on every machine.

### `quick.config.toml`

```toml
model = "gpt-5.4"
model_reasoning_effort = "low"
model_context_window = 1000000
model_auto_compact_token_limit = 900000
model_verbosity = "low"
service_tier = "normal"
```

Use for:

- quick edits
- shell-heavy work
- short diagnostics
- lowest-latency Codex loops

### `deep-review.config.toml`

```toml
model = "gpt-5.4"
model_reasoning_effort = "high"
model_context_window = 1000000
model_auto_compact_token_limit = 850000
model_verbosity = "medium"
service_tier = "normal"
```

Use for:

- code review
- repo mapping
- non-trivial debugging
- broad planning

### `xhigh-long.config.toml`

```toml
model = "gpt-5.4"
model_reasoning_effort = "xhigh"
model_context_window = 1000000
model_auto_compact_token_limit = 800000
model_verbosity = "medium"
service_tier = "normal"
```

Use for:

- ambiguous incidents
- architecture work
- hard debugging
- long reasoning with deliberate headroom for hidden reasoning/output overhead

### `frontier.config.toml`

```toml
model = "gpt-5.5"
model_reasoning_effort = "high"
model_context_window = 272000
model_auto_compact_token_limit = 240000
model_verbosity = "medium"
service_tier = "normal"
```

Use for:

- work that fits comfortably below `~240k` effective input
- cases where `gpt-5.5` quality matters more than long context

Do not use this profile to chase 1M context. In the current Codex local catalog, `gpt-5.5` stays capped at `272000`.

## Rules

- Do not set `max_tokens`, `max_output_tokens`, `max_input_tokens`, or similar API-only knobs in Codex `config.toml`.
- Do not re-add `[notice.model_migrations]` mapping `gpt-5.4` to `gpt-5.5` on these machines.
- Keep `service_tier = "normal"` as the fleet default. Fast/priority is not the canonical baseline.
- Lower `model_auto_compact_token_limit` as reasoning effort rises. Do not push `xhigh` to `900000`.
- Keep heavy MCPs out of the default startup path. Use `docs/operations/codex-mcp-startup-standard.md` for the current MCP split, smoke checks, Cloudflare vault launcher, and rollback.

## Validation

Base config:

```bash
codex doctor --summary --ascii --no-color
```

Relevant lines:

```bash
grep -E '^(model|model_reasoning_effort|model_context_window|model_auto_compact_token_limit|model_verbosity|service_tier) =' ~/.codex/config.toml
grep -E '^(model|model_reasoning_effort|model_context_window|model_auto_compact_token_limit|model_verbosity|service_tier) =' ~/.codex/*.config.toml
```

If `codex` is not in the non-interactive shell PATH, resolve it explicitly:

```bash
CODEX_BIN="$(command -v codex || ls "$HOME"/.nvm/versions/node/*/bin/codex 2>/dev/null | head -n1 || ls "$HOME"/.local/bin/codex 2>/dev/null | head -n1)"
"$CODEX_BIN" --version
"$CODEX_BIN" doctor --summary --ascii --no-color
```

## Rollout status - 2026-07-02

- `GIOVANNI-W11-PC`: local default and profiles aligned with this standard.
- `atius-srv-1`: base config and all 4 profiles applied; doctor loaded the config successfully.
- `atius-srv-2`: base config and all 4 profiles applied; doctor loaded the config successfully.
- `atius-srv-3`: base config and all 4 profiles applied; doctor loaded the config successfully.
- `horistic-srv`: base config and all 4 profiles applied; standalone `codex` resolved to `0.142.5`, non-interactive `zsh` PATH was fixed with `~/.zshenv`, old NVM `@openai/codex` was removed, and `doctor` passed with `0 fail`.

## Backups

Rollout backups created on the Linux hosts follow this pattern:

```text
~/.codex/config.toml.bak-<timestamp>-fleet-codex-standard
~/.codex/<profile>.config.toml.bak-<timestamp>-fleet-codex-standard
```

The local Windows machine already had a prior backup before the profile rollout:

```text
C:\Users\muniz\.codex\config.toml.bak-20260702T042936-0300-context-profiles
```

## Service tier enforcement - 2026-07-04

Audit and enforcement completed across `GIOVANNI-W11-PC`, `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and `horistic-srv`.

- Canonical explicit value: `service_tier = "normal"` (`Padrão`).
- Corrected local base config from `priority` to `normal`.
- Corrected `atius-srv-1` and `atius-srv-3` base configs from `default` to `normal`.
- Corrected GSD agent configs on `GIOVANNI-W11-PC`, `atius-srv-1`, and `atius-srv-2` from `flex` to `normal`, because the fleet policy is now “always Padrão”.
- Final verification: `NON_NORMAL_COUNT = 0` for active Codex TOML files with `service_tier`, excluding backups/cache/temp.
- Detailed evidence: `docs/operations/codex-service-tier-audit-2026-07-04.md`.
- DbOmniFleet policy registered via `omni fleet registry upsert-policy` with `target_id = codex-service-tier`.

