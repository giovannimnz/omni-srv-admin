# Phase 43: Codex MCP Bootstrap Hardening - Context

**Gathered:** 2026-07-04
**Status:** Ready for research
**Source:** local Codex runtime inspection on `GIOVANNI-W11-PC`, existing runtime docs, `codex doctor`, `codex mcp list/get`, and repo planning context

<domain>
## Phase Boundary

This phase hardens the local Codex bootstrap on `GIOVANNI-W11-PC`.

It plans changes to the local Codex runtime surface first, not server-side app
workloads. The implementation phase may touch `C:\Users\muniz\.codex`,
profile files, repo docs, and a local smoke script, but should not mutate OCI,
Cloudflare, Obsidian server config, or remote browsers just to suppress local
startup noise.

The target behavior is a lean default Codex startup with opt-in MCP profiles.
The phase does not assume that every configured MCP must always be enabled.

</domain>

<decisions>
## Implementation Decisions

- **D-01:** Daily default Codex startup on Windows must be lean and stable, not "everything enabled all the time".
- **D-02:** Optional MCP groups move out of the base `config.toml` and into named opt-in profiles loaded with `codex -p <profile>`.
- **D-03:** Missing secrets such as `CF_GLOBAL_API_KEY` are configuration-prerequisite issues, not timeout issues; the fix is not to mirror secrets blindly just to remove warnings.
- **D-04:** Remote HTTP MCP reachability problems, especially `obsidian_rest`, must be treated as reachability/VPN issues first; increasing timeout alone is not an acceptable primary fix.
- **D-05:** Heavy stdio MCPs launched through `npx` and `uv` must either leave the baseline or receive explicit startup budgets and stable command paths.
- **D-06:** Always-on startup must avoid `@latest` package resolution on the hot path whenever a pinned/local equivalent is viable.
- **D-07:** Validation must classify startup state as `ok`, `disabled`, `missing-env`, `unreachable`, or `slow-start`; "timed out" is not sufficient diagnosis by itself.
- **D-08:** Rollback must be one-file-at-a-time through backups of `config.toml` and every new profile file before mutation.
- **D-09:** The default Windows baseline keeps only MCPs that are both high-frequency and currently stable; everything else must justify being always-on.
- **D-10:** Documentation must show exact profile names, when to use each one, and the verification commands after switching profiles.
- **D-11:** No Cloudflare token, Obsidian bearer token, OCI credential, or copied auth header value may be written to Git, `.planning`, docs, logs, or shell history.

### D-01 | Lean default
The current baseline starts too many MCPs for a normal coding session. The
default startup should favor responsiveness and predictable tool availability.

### D-02 | Opt-in profile split
Browser, OCI, Cloudflare, knowledge, and lab tools should be activatable on
demand through explicit Codex profiles rather than forced into every startup.

### D-03 | Missing-env handling
`cloudflare-api` currently depends on `CF_GLOBAL_API_KEY`. If that env var is
not intentionally provisioned on Windows, the correct plan is disable-by-
default or opt-in profile, not secret sprawl.

### D-04 | Reachability before timeout
`obsidian_rest` already has `startup_timeout_sec = 120` and still fails
reachability checks. The phase must preserve this distinction so the fix does
not degenerate into "just raise every timeout".

### D-05 | Heavy stdio MCPs
`playwright-*`, `chrome-devtools`, `memory`, `filesystem`,
`sequentialthinking`, and the OCI MCPs all start via `npx` or `uv`; that makes
them the primary suspects for cold-start contention on a saturated bootstrap.

### D-06 | No `@latest` on the hot path
Package-resolution drift on every start is undesirable for daily bootstrap. If
the browser/tooling MCPs remain in any commonly used profile, pinning or local
wrappers should replace `@latest`.

### D-07 | Failure classification
The implementation must expose why a server is unavailable. Missing env, VPN
down, browser path missing, and slow `uv` cold-start are materially different
operator actions.

### D-08 | Backup-first rollback
The local Codex runtime is a daily operator surface. Every touched file needs a
dated backup before edits so rollback stays mechanical.

### D-09 | Baseline server set
The baseline server set should be as small as possible while preserving the
most-used tooling. `node_repl` and `gbrain` are the strongest keep candidates.

### D-10 | Documented usage
The operator needs one canonical doc that says which profile to use for
browser work, OCI work, Cloudflare work, knowledge work, and experimental
lab-style helpers.

### D-11 | Secret hygiene
Local config cleanup must not become an excuse to replicate or expose secrets
that are intentionally scoped elsewhere.

</decisions>

<canonical_refs>
## Canonical References

### Local Codex runtime truth
- `C:\Users\muniz\.codex\config.toml` - active MCP inventory and runtime defaults.
- `C:\Users\muniz\.codex\mcp-patch.toml` - historical MCP additions that increased the baseline surface.
- `codex doctor --json` on `GIOVANNI-W11-PC` - current runtime truth for MCP optional issues.
- `codex mcp list` and `codex mcp get <name>` - current configured transport, env var, timeout, and auth shape.

### Repo docs and prior standard
- `docs/operations/codex-runtime-standard.md` - current fleet runtime standard, which does not yet define MCP bootstrap policy.
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` - authoritative record for Obsidian REST/MCP endpoint `10.1.1.1:27124`.
- `.planning/ROADMAP.md` and `.planning/REQUIREMENTS.md` - phase/requirement source of truth for the new planning slice.

### Historical context
- GBrain note `2026-07-02-codex-runtime-standard-fleet` - prior fleet-standard runtime decisions and backup pattern.
- `C:\Users\muniz\.codex\config.toml.bak-20260702T042936-0300-context-profiles` - known local backup from the previous runtime standardization pass.

</canonical_refs>

<specifics>
## Specific Ideas

- Split the current base config into:
  - lean baseline
  - `knowledge-mcp`
  - `browser-mcp`
  - `oci-mcp`
  - `cloud-ops-mcp`
  - `lab-mcp`
- Keep `obsidian_rest` out of the lean baseline unless reachability can be guaranteed during normal Windows startup.
- Use the phase to add one operator-facing smoke script that can test base startup and each profile intentionally.
- Prefer pinned package versions or local wrapper commands over `@latest` in any profile expected to be used frequently.

</specifics>

<deferred>
## Deferred Ideas

- Cross-host rollout of the same MCP profile split to `atius-srv-1/2/3` or `horistic-srv` is deferred.
- Adding or rotating Cloudflare secrets on Windows is deferred unless a later execution gate explicitly approves it.
- Reworking the Obsidian server-side endpoint itself is deferred; this phase only plans the local consumer-side behavior.
- Any change to Codex Desktop internal `.codex/settings.json` semantics is deferred unless implementation proves that the app honors it for this setup.

</deferred>

---

*Phase: 43-codex-mcp-bootstrap-hardening*
*Context gathered: 2026-07-04*
