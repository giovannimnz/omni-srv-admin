# Codex Fleet Runtime Standard

Canonical Codex runtime standard for the managed machines:

- `C:\Users\muniz\.codex` on `GIOVANNI-W11-PC`
- `/home/ubuntu/.codex` on `atius-srv-1`
- `/home/ubuntu/.codex` on `atius-srv-2`
- `/home/ubuntu/.codex` on `atius-srv-3`
- `/home/horistic/.codex` on `horistic-srv`

## GPT-5.4 long-context profile baseline

Use this in an explicit GPT-5.4 profile when 1M context is needed. Do not
copy these limits into a base config that is operating GPT-5.6 Sol/Luna:

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

## GPT-5.6 Sol/Luna base policy — 2026-08-21

Applied to the base `config.toml` on `atius-srv-1`, `atius-srv-2`,
`atius-srv-3`, and `horistic-srv`:

```toml
model_context_window = 872_000
model_auto_compact_token_limit = 800_000
model_auto_compact_token_limit_scope = "total"
```

These top-level keys apply to the active model. The four host caches
(`client_version=0.149.0`) advertise the same GPT-5.6 Sol/Luna contract:

| Model | context_window | max_context_window | effective_context_window_percent | Effective limit |
|---|---:|---:|---:|---:|
| `gpt-5.6-sol` | 272_000 | 872_000 | 95 | 828_400 |
| `gpt-5.6-luna` | 272_000 | 872_000 | 95 | 828_400 |

`900_000` is above the live maximum. `850_000` would trigger automatic
compaction after the effective limit. `800_000` keeps `28_400` tokens of
headroom. Use an explicit `gpt-5.4` profile to recover the 1M GPT-5.4 policy;
do not claim that these base keys create a 900K/1M entitlement for another
backend model.

Backups were byte-verified before each edit:

- `atius-srv-1`: `/home/ubuntu/.codex/config.toml.bak-gpt56-sol-luna-context-20260821T042510Z`
- `atius-srv-2`: `/home/ubuntu/.codex/config.toml.bak-gpt56-sol-luna-context-20260821T042314Z`
- `atius-srv-3`: `/home/ubuntu/.codex/config.toml.bak-gpt56-sol-luna-context-20260821T042314Z`
- `horistic-srv`: `/home/horistic/.codex/config.toml.bak-gpt56-sol-luna-context-20260821T042517Z`

Validation:

- All four TOMLs parse with `tomllib` and re-read the exact policy above.
- `atius-srv-2`, `atius-srv-3`, and `horistic-srv`: `codex --strict-config doctor --summary --no-color` reports `0 fail`.
- `atius-srv-1`: default `/usr/local/bin/codex` loads the policy but reports an independent install/update-path drift because it resolves to NVM `v24.13.1` while npm global resolves to NVM `v24.18.0`. The aligned `~/.nvm/versions/node/v24.18.0/bin/codex --strict-config doctor --summary --no-color` passed with `20 ok, 0 fail`. Repair the default path separately; it is not a context-policy failure.

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

### SRV-3 Codex 0.144.1 compatibility exception

On `atius-srv-3`, Codex `0.144.1` warns that explicit
`service_tier = "normal"` is not advertised for `gpt-5.4` and omits it from
requests. The base config and four profiles therefore omit this key; omitted
means standard routing and does not opt into Fast/priority. The runtime also
uses `[features].hooks`, not deprecated `[features].codex_hooks`.

Canonical binaries on 2026-07-12:

- `/home/ubuntu/.local/bin/codex` -> `0.144.1`
- login `zsh` `codex` -> `0.144.1`
- `/usr/local/bin/codex` -> the same user-managed `0.144.1`

The build CPU guard resolves `npm` and `npx` to the newest installed NVM
runtime and prepends that NVM `bin` directory before execution. This keeps
build/install commands under the 20 percent cgroup while ensuring `npm root
-g`, `codex update`, and the running Codex package share the same prefix.

The Cloudflare plugin and its OAuth MCP are disabled only on the Wayland
runtime. Cloudflare automation continues through the Vault-hydrated ATIUS
control path; re-enable the plugin only when a headless Chromium OAuth session
can complete `codex mcp login cloudflare-api`.

Validation on `atius-srv-3`:

- native `gpt-5.6-sol` -> `GPT56_NATIVE_OK`
- `codex doctor --summary --ascii --no-color` -> `18 ok`, `0 warn`, `0 fail`
- TUI startup smoke -> no `codex_hooks`, Cloudflare login, or unsupported
  service-tier warning

## MCP approval standard

Keep MCP approval handling aligned to this baseline on every Codex host:

```toml
approval_policy = "never"
approvals_reviewer = "auto_review"
```

For every configured MCP server table, keep:

```toml
default_tools_approval_mode = "approve"
```

For `chrome-devtools`, keep per-tool overrides for the common browser actions used in live sessions, such as:

```toml
[mcp_servers.chrome-devtools.tools.click]
approval_mode = "approve"
```

This does two things:

- normal MCP tool calls do not stop to ask the human by default
- if an MCP tool still triggers an approval path because of server/tool semantics, Codex routes it to `auto_review` instead of prompting the user directly

Operational caveat:

- OpenAI docs still reserve the right for destructive app/MCP tool calls to require approval when the tool advertises destructive annotations. In practice, the fleet baseline above is the strongest supported "do not ask the human" posture for Codex config.
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
- 2026-07-12: MCP approval policy normalized across local W11 + `atius-srv-1/2/3` + `horistic-srv`: `approval_policy = "never"`, `approvals_reviewer = "auto_review"`, and `default_tools_approval_mode = "approve"` on configured MCP servers. Goal: stop human approval prompts such as `chrome-devtools` `click`.

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
