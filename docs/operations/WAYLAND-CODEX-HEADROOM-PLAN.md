# Wayland Codex Headroom Plan

## Objective

Integrate Headroom into the Codex CLI already used by Wayland on
`atius-srv-3`, while preserving the runtime chain:

```text
Wayland -> codex-acp -> Codex CLI -> Headroom loopback proxy -> OpenAI
```

Headroom does not replace `codex-acp`, the remote ACP gateway, Wayland session
handling, or the Router Codex channel.

## Pinned baseline

- package: `headroom-ai[all]==0.31.0`
- upstream tag: `v0.31.0`
- upstream commit: `55efb1c77d5b67f7ad0620372c6256c8b0547591`
- PyPI sdist SHA-256: `a13f9764be168e4d075fd80ff6ee5d47a9febe0152b82ad28bab0e949fcd9bd3`
- platform: Linux ARM64 wheel, Python 3.10+

Do not use `latest` or `headroom update` in the managed runtime. Revalidate a
new release in a separate canary before changing this pin.

Primary upstream evidence:

- `https://github.com/headroomlabs-ai/headroom/tree/v0.31.0`
- `https://pypi.org/project/headroom-ai/0.31.0/`

## Ownership boundary

Session `019f2ba1-1982-7c03-a17d-3ce28c589ac1` owns current Wayland,
`codex-acp`, ACPX/OpenClaw gateway, TLS, Upgrade authentication, approval flow,
and model-selector work. Session `019f3e9a-9964-7912-a982-65596e9954d3`
owns concurrent Router/model work.

Until those owners release their files, this plan must not edit:

- `/home/ubuntu/GitHub/wayland`
- `/home/ubuntu/GitHub/codex-acp`
- `/home/ubuntu/GitHub/containers/router-ai-atius`
- active ACP gateway or Wayland systemd units

The NFS fleet mounts and this runbook are independent and may proceed.

## Critical safety finding

`headroom wrap codex` is not a read-only launcher. In v0.31.0 it can mutate the
active `CODEX_HOME` by:

- rewriting `config.toml` and creating `config.toml.headroom-backup`;
- registering MCP servers and injecting guidance into `AGENTS.md`;
- changing Codex thread `model_provider` values in SQLite stores;
- starting or reusing a proxy and changing routing for the whole home.

Therefore, never run `headroom wrap codex` against the active
`/home/ubuntu/.codex` while Codex/ACP sessions are running.

## Execution waves

### Wave 0: gates and backup

1. Confirm both owner sessions are idle or have released the target files.
2. Confirm Codex OAuth is healthy without Headroom. A `token_invalidated`,
   `refresh_token_invalidated`, 401, or 403 blocks rollout.
3. Confirm the final model catalog works natively so model drift is not
   misdiagnosed as a proxy regression.
4. Back up the active Codex config/auth and Wayland/codex-acp service units.
5. Record hashes and permissions without logging token contents.

Stop if native Codex, ACP, or model selection is not healthy.

### Wave 1: isolated Headroom canary

Create `/home/ubuntu/.codex-wayland-headroom-canary` with mode `0700`. Copy only
the minimum config and authenticated state required for the canary, preserving
`0600` on secret files. Do not copy or symlink SQLite/session stores.

Install the pinned package as an `ubuntu` user-level `uv tool`. Verify the
resolved executable path and `headroom --version`. Start a user systemd service
bound only to `127.0.0.1:8787`; do not expose the proxy through Apache,
Cloudflare, OCI NSGs, or NFS.

Prepare only the isolated Codex home:

```bash
CODEX_HOME=/home/ubuntu/.codex-wayland-headroom-canary \
  headroom wrap codex --prepare-only --port 8787 \
  --no-context-tool --no-mcp --no-tokensave --no-serena
```

The first canary tests only proxy routing. MCP, memory, learning, output shaping,
and code-graph features stay disabled until transport parity passes.

### Wave 2: direct Codex parity

Run native and Headroom canaries against the same non-destructive prompts.
Validate:

- ChatGPT OAuth/account identity is preserved;
- HTTP `/v1/responses` and WebSocket streams both reach completion;
- model, reasoning effort, tools, `apply_patch`, cancellation, and reconnect work;
- `headroom doctor`, proxy health, and stats report routed requests;
- compression reports non-zero transformed content on an eligible large tool
  output, not merely proxied requests with zero savings;
- no tokens, raw Authorization headers, or prompt bodies enter journals.

Stop on any 401/403, missing `api.responses.read`, incomplete
`response.completed`, reconnect loop, zero-transform false positive, or model
catalog mismatch.

### Wave 3: ACP canary

After direct parity, launch `codex-acp` manually with the isolated
`CODEX_HOME`. Keep the production wrapper unchanged. Validate ACP initialize,
new session, prompt, tool call, permission request, cancel, resume, and clean
shutdown.

Headroom remains behind Codex. The ACP protocol, adapter binary, gateway token,
and remote WebSocket contract do not change.

### Wave 4: Wayland integration

Only after ownership release, add a reversible Wayland-scoped selection for the
Headroom Codex home in the existing `codexConfig.ts` / `AcpAgentManager.ts`
launch seam or the ATIUS codex-acp wrapper. Do not make Headroom the fallback
for every shell Codex process on the host.

Canary one Wayland project first. Browser validation must use Chromium headless
through Chrome DevTools. Prove conversation creation, streaming, approvals,
cancel/resume, selected model/effort, and savings telemetry before broadening.

### Wave 5: optional capabilities

Enable one feature at a time in this order: Headroom retrieve MCP, memory,
context-tool/code-graph, learning, then output shaping. Each addition requires a
separate before/after validation and rollback checkpoint. Headroom memory does
not replace Obsidian or GBrain.

## Rollback

1. Point the Wayland Codex launch seam back to `/home/ubuntu/.codex`.
2. Restart only the affected Wayland/codex-acp runtime after active sessions
   drain.
3. Stop and disable the loopback Headroom service.
4. Preserve the canary home for forensics; do not merge its SQLite state into
   the native home.
5. If an active home was ever wrapped, use the matching `CODEX_HOME` with
   `headroom unwrap codex`, verify the backup hash, and inspect the diff before
   restarting Codex.
6. Re-run native Codex, ACP, Wayland, auth, model, and browser smokes.

Rollback success means the original `Wayland -> codex-acp -> codex` path works
without Headroom and no session/provider records were lost.

## Completion evidence

- pinned package/version/hash and systemd unit state;
- native and Headroom canary transcripts with secrets redacted;
- proxy health plus eligible request savings evidence;
- ACP lifecycle smoke results;
- Chromium headless Chrome DevTools Wayland smoke results;
- rollback rehearsal;
- updated fork-sync guards, Obsidian note, and GBrain facts.
