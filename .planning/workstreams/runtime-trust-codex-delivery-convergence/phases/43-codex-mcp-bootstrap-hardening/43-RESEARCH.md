# Phase 43: Codex MCP Bootstrap Hardening - Research

## RESEARCH COMPLETE

**Question:** What actually causes the noisy MCP startup behavior on `GIOVANNI-W11-PC`, and what planning pattern will remove it without breaking the operator's daily Codex workflow?

**Primary sources:** local `codex doctor --json`, `codex mcp list`, `codex mcp get`, `C:\Users\muniz\.codex\config.toml`, `C:\Users\muniz\.codex\mcp-patch.toml`, repo runtime docs, and GBrain runtime-standard history.

## Findings

### 1. The problem is not one timeout bug

The startup warnings represent at least four distinct classes of failure:

- missing secret: `cloudflare-api` requires `CF_GLOBAL_API_KEY`
- unreachable remote HTTP endpoint: `obsidian_rest`
- heavy stdio bootstrap without explicit timeout: browser, lab, and OCI MCPs
- excessive baseline breadth: too many MCPs enabled in the default runtime

Treating all of them as "raise timeout" would hide root causes and keep the
startup noisy.

### 2. The baseline is oversized for daily use

Current local inspection shows:

- `18` MCP servers configured
- `16` stdio servers
- `2` streamable HTTP servers

This is too broad for a daily default startup on the workstation, especially
because the enabled set includes:

- 8 OCI MCP servers
- 2 Playwright MCP servers
- Chrome DevTools MCP
- lab-style helpers (`memory`, `filesystem`, `sequentialthinking`)
- remote knowledge/auth surfaces (`obsidian_rest`, `cloudflare-api`)

### 3. `obsidian_rest` already disproves the "just increase timeout" theory

`obsidian_rest` already has `startup_timeout_sec = 120`, but `codex doctor`
still reports:

- optional reachability failed
- HEAD connect failed
- GET connect failed

This means the real blocker is transport reachability to
`https://10.1.1.1:27124/mcp/`, not a 30-second limit.

### 4. `cloudflare-api` is a prerequisite issue, not a bootstrap issue

`cloudflare-api` is configured as a streamable HTTP MCP with:

- `url = "https://mcp.cloudflare.com/mcp"`
- `bearer_token_env_var = "CF_GLOBAL_API_KEY"`

If `CF_GLOBAL_API_KEY` is not set on Windows, the correct runtime policy is
disable-by-default or opt-in profile. Copying secrets locally just to silence
startup warnings is the wrong default.

### 5. Heavy stdio servers are launched through `npx` and `uv`

The slow-start candidates are exactly the servers that start through package
resolution or Python environment boot:

- `memory`, `filesystem`, `sequentialthinking`, `chrome-devtools`
- `playwright-desktop`, `playwright-mobile`
- `oci-api-*`, `oci-compute-*`

The browser MCPs also use `@latest`, which adds version-resolution drift to the
startup path.

### 6. There is no existing MCP bootstrap policy doc

`docs/operations/codex-runtime-standard.md` already standardizes:

- model
- reasoning effort
- context window
- service tier

But it does **not** yet standardize:

- which MCPs belong in the daily baseline
- which MCPs should be profile-only
- timeout classes by server type
- cold-start smoke commands
- rollback rules for MCP config changes

### 7. There is no `settings.json` override in place today

No global or project `.codex/settings.json` exists in the current setup. The
primary, proven surface is still `C:\Users\muniz\.codex\config.toml`, and Codex
profiles already have first-class CLI support through `codex -p <profile>`.

Because of that, the safest primary plan is profile-splitting in `config.toml`
land rather than assuming a Desktop-only toggle path.

## Recommended architecture

### Lean baseline

Keep only the MCPs that are both:

- high-frequency in daily work
- currently stable on this machine

The strongest lean-baseline candidates are:

- `node_repl`
- `gbrain`

Everything else should justify remaining in the always-on path.

### Opt-in profiles

Split the rest into named Codex profiles:

- `knowledge-mcp` - `obsidian_rest` and related note-store surfaces
- `browser-mcp` - `chrome-devtools`, `playwright-desktop`, `playwright-mobile`
- `oci-mcp` - all `oci-api-*` and `oci-compute-*`
- `cloud-ops-mcp` - `cloudflare-api`
- `lab-mcp` - `memory`, `filesystem`, `sequentialthinking`

### Timeout and pinning policy

- do not use timeout inflation as the primary fix for unreachable HTTP servers
- set explicit `startup_timeout_sec` only for profile servers that remain
  intentionally enabled
- remove `@latest` from any commonly used browser MCP profile and prefer pinned
  or local commands where viable

### Validation policy

One smoke path should validate:

- lean baseline clean boot
- per-profile preflight
- per-profile `codex doctor` result
- failure classification without secrets

## Recommendation

Proceed with two executable plans:

1. Split the local MCP inventory into a lean baseline plus named opt-in
   profiles, with backup-first rollback and new operator docs.
2. Harden the non-baseline profiles with explicit startup budgets, preflight
   checks, pinned commands where justified, and a repeatable cold-start smoke
   script.
