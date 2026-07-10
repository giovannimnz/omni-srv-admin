# Codex GBrain + Obsidian MCP Contract

Status: active standard as of 2026-07-05.

## Purpose

Centralize the ATIUS Codex knowledge MCP pattern under one public edge:

- `https://mcp.atius.com.br/gbrain`
- `https://mcp.atius.com.br/obsidian`

This document is the repo handoff for the operational session that moved the
fleet from older SSH and ad hoc MCP paths to the current HTTP pattern.

## Canonical Names

Use exactly these two Codex MCP entries:

- `gbrain_http`
- `obsidian_http`

Do not use retired names such as:

- `http_gbrain`
- `http_obsidian`
- `obsidian_rest`
- old SSH-backed `gbrain` entries as the fleet default

Both public MCPs use:

- `Authorization: Bearer $ATIUS_MCP_TOKEN`

Source of truth for the token:

- Vault profile: `atius-mcp`
- Vault path: `kv/atius/atius-mcp/api`

Runtime `.env`, `.zshrc`, user env vars, and process env are hydration caches
only. They are not the authority.

## Topology

Public edge:

- `mcp.atius.com.br` terminates TLS on the SRV-1 edge stack.

Backend routing:

- `/gbrain` -> local GBrain HTTP MCP on `127.0.0.1:3131`
- `/obsidian` -> Obsidian Local REST MCP on `10.11.1.11:27124`

Backends remain private/internal. Clients should target only the public URLs
unless they are doing controlled origin-only diagnostics.

## Protocol Behavior

The user-facing URLs are HTTP endpoints, but the application protocol is MCP
over JSON-RPC.

Expected behavior:

1. Client sends `POST` JSON-RPC `initialize`.
2. MCP server returns its negotiated capabilities.
3. For Obsidian, preserve `Mcp-Session-Id`.
4. Client sends `notifications/initialized`.
5. Client calls `tools/list` and later tool methods.

Important distinctions:

- `POST` is the main transport for MCP requests such as `initialize`,
  `tools/list`, and tool calls.
- `GET` may exist for auxiliary endpoints such as GBrain health
  (`/gbrain/health`) or stream-oriented transport details, but it is not the
  primary contract for normal Codex tool use.
- `PUT` is not the normal public MCP contract here. `PUT` only appears in
  fallback or non-MCP APIs, such as direct note/file writes outside the Codex
  MCP flow.

Session behavior:

- `obsidian_http` is sessionful. After `initialize`, the client must preserve
  `Mcp-Session-Id` and complete `notifications/initialized` before later tool
  calls.
- `gbrain_http` validated successfully with normal MCP `initialize` and a
  stateless-feeling follow-up flow in the tested setup, but clients should
  still treat MCP negotiation as required.

## Validation Pattern

Validated fleet on 2026-07-05:

- `atius-srv-1`
- `atius-srv-2`
- `atius-srv-3`
- `horistic-srv`
- `GIOVANNI-W11-PC`

Validation classes used in the rollout:

### 1. Edge and backend health

- GBrain local backend health on `127.0.0.1:3131/health`
- public edge reachability on `https://mcp.atius.com.br/gbrain`
- public MCP initialization against both `/gbrain` and `/obsidian`

On the public edge, treat `POST initialize` as the canonical health check for
GBrain MCP. `/gbrain/health` is auxiliary and may not be exposed on every edge
revision.

### 2. Auth validation

- valid `ATIUS_MCP_TOKEN` returns successful MCP `initialize`
- invalid or stale token returns `401`

### 3. Codex client validation

- `codex mcp add gbrain_http --url https://mcp.atius.com.br/gbrain --bearer-token-env-var ATIUS_MCP_TOKEN`
- `codex mcp add obsidian_http --url https://mcp.atius.com.br/obsidian --bearer-token-env-var ATIUS_MCP_TOKEN`
- `codex mcp list` confirms both entries on each host

### 4. Obsidian session validation

- `initialize` succeeds
- same session preserves `Mcp-Session-Id`
- `notifications/initialized` follows before normal tool use

For Windows specifically, remember that Codex Desktop may need a restart after
token rotation so the new user env var is inherited.

## Production Expectations

Expected performance profile:

- Normal MCP overhead is low compared with model inference and tool payloads.
- The heavier cost is usually indirect: `tools/list`, large tool manifests,
  note payload size, and context pressure inside Codex.
- Network latency matters more than CPU for ordinary MCP operations.
- Obsidian is usually more sensitive to session and plugin state than raw CPU.
- GBrain cost depends more on the downstream query/index workload and Postgres
  state than on the MCP transport itself.

Practical consequences:

- Keep default Codex startup lean and load optional MCP sets through profiles or
  launchers when possible.
- Use profile scoping to avoid loading many unrelated MCPs into the same Codex
  session.
- Prefer narrow reads and targeted writes instead of broad tool dumps.

## Failure Modes

Most likely breakpoints:

- stale `ATIUS_MCP_TOKEN` after rotation
- token loaded from the wrong source instead of Vault
- public DNS drift versus local `hosts` overrides
- Obsidian plugin up but session negotiation incomplete
- backend service active locally but edge proxy misrouted

Fast checks:

1. confirm the token source is Vault `kv/atius/atius-mcp/api`
2. confirm the Codex entry names are `gbrain_http` and `obsidian_http`
3. confirm GBrain local health on `127.0.0.1:3131/health`
4. confirm MCP `initialize` against public `/gbrain` and `/obsidian`
5. on Obsidian failures, verify `Mcp-Session-Id` handling before deeper debug

## Related Docs

- [Codex MCP Startup Standard](./codex-mcp-startup-standard.md)
- [Cloudflare Configuration](../CLOUDFLARE.md)
- [Atius Secrets Vaults](../security/atius-secrets-vaults.md)
- [ATIUS Fleet Network Port Map](./ATIUS-FLEET-NETWORK-PORT-MAP.md)
