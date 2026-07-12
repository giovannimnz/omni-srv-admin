# Phase 48: Codex OAuth and Wayland Remote ACP Convergence - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 5 inferred Phase 48 execution lanes
**Analogs found:** 5 / 5

## File Classification

Context/research define execution lanes and proof artifacts, not concrete new source
files inside this repo. The planner should treat the entries below as implied
phase artifacts/workstreams and reuse the listed in-repo analogs.

| Planned File / Lane | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `48-native-oauth-proof.md` | test | request-response | `docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md` | exact |
| `48-local-acp-lifecycle.md` | test | request-response | `docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md` + `modules/fork-sync/projects/codex-acp/UPSTREAM-SYNC-GUARDS.md` | exact |
| `48-remote-wss-lifecycle.md` | service | request-response | `modules/fork-sync/projects/codex-acp/runtime/openclaw.patch.json5` + `openclaw-codex-acp.service` + `hydrate-gateway-env.sh` | exact |
| `48-wayland-browser-lifecycle.md` | test | streaming | `docs/operations/wayland-managed-runtime.md` + `.planning/phases/49-wayland-codex-headroom/49-VALIDATION.md` | exact |
| `48-router-cpu-verification.md` | test | batch | `docs/operations/resource-governor.md` + `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md` | exact |

## Pattern Assignments

### `48-native-oauth-proof.md` (test, request-response)

**Analog:** `docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md`

**Auth gate pattern** (lines 64-72):
```markdown
1. Confirm both owner sessions are idle or have released the target files.
2. Confirm Codex OAuth is healthy without Headroom. A `token_invalidated`,
   `refresh_token_invalidated`, 401, or 403 blocks rollout.
3. Confirm the final model catalog works natively so model drift is not
   misdiagnosed as a proxy regression.
4. Back up the active Codex config/auth and Wayland/codex-acp service units.
5. Record hashes and permissions without logging token contents.

Stop if native Codex, ACP, or model selection is not healthy.
```

**Renewable prompt proof pattern** (lines 98-110):
```markdown
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
```

**Completion evidence pattern** (lines 157-165):
```markdown
- pinned package/version/hash and systemd unit state;
- native and Headroom canary transcripts with secrets redacted;
- proxy health plus eligible request savings evidence;
- ACP lifecycle smoke results;
- Chromium headless Chrome DevTools Wayland smoke results;
- rollback rehearsal;
- updated fork-sync guards, Obsidian note, and GBrain facts.
```

**Tighter adjacent validation gate** (`.planning/phases/49-wayland-codex-headroom/49-VALIDATION.md`, lines 5-9, 17-18):
```markdown
- Proxy listens only on loopback and journals contain no auth headers/prompts.
- Active `/home/ubuntu/.codex` config, AGENTS and SQLite hashes do not change.
- Isolated direct Codex passes OAuth, HTTP Responses, WebSocket completion,
  tools, apply_patch, cancel/reconnect and model/effort parity.

- Any mutation of active Codex SQLite/provider tags.
- 401/403, missing scope, incomplete WebSocket completion or reconnect loop.
```

---

### `48-local-acp-lifecycle.md` (test, request-response)

**Analogs:** `docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md`, `modules/fork-sync/projects/codex-acp/UPSTREAM-SYNC-GUARDS.md`

**Lifecycle order pattern** (`WAYLAND-CODEX-HEADROOM-PLAN.md`, lines 113-121):
```markdown
After direct parity, launch `codex-acp` manually with the isolated
`CODEX_HOME`. Keep the production wrapper unchanged. Validate ACP initialize,
new session, prompt, tool call, permission request, cancel, resume, and clean
shutdown.

Headroom remains behind Codex. The ACP protocol, adapter binary, gateway token,
and remote WebSocket contract do not change.
```

**Runtime invariants pattern** (`modules/fork-sync/projects/codex-acp/UPSTREAM-SYNC-GUARDS.md`, lines 17-24):
```markdown
- Track the Codex Rust crates used by the installed Codex CLI.
- Preserve `agent-profile` loading from `/home/ubuntu/.codex/agents/*.toml`.
- Advertise model, reasoning effort, service tier, and Power configuration.
- Keep `plugins.allow=["acpx"]`; no discovered plugin may auto-load implicitly.
- Run through `scripts/codex-acp-atius-wrapper.sh` so the single-user runtime
  keeps `CODEX_HOME=/home/ubuntu/.codex` and `HERMES_HOME=/home/ubuntu/.hermes`.
- Keep the default Codex sandbox policy sourced from the canonical
  `/home/ubuntu/.codex/config.toml` (`danger-full-access` in this environment).
```

**Post-change verification command pattern** (`modules/fork-sync/projects/codex-acp/UPSTREAM-SYNC-GUARDS.md`, lines 28-35):
```bash
cd /home/ubuntu/GitHub/codex-acp
CARGO_BUILD_JOBS=1 cargo check
CARGO_BUILD_JOBS=1 cargo test --lib
```

Planner note:
Phase 48 needs lifecycle transcript reuse from this order, but the exact local
ACP prompt harness command is not pinned in the gathered repo files. Treat that
missing command as an execution-time gap, not as license to reorder the matrix.

---

### `48-remote-wss-lifecycle.md` (service, request-response)

**Analogs:** `modules/fork-sync/projects/codex-acp/runtime/openclaw.patch.json5`, `openclaw-codex-acp.service`, `hydrate-gateway-env.sh`, `modules/fork-sync/projects/codex-acp/UPSTREAM-SYNC-GUARDS.md`

**Network/auth invariant pattern** (`modules/fork-sync/projects/codex-acp/UPSTREAM-SYNC-GUARDS.md`, lines 8-13):
```markdown
- Bind the gateway to the SRV-3 OCI/DRG address `10.13.1.13:18789`.
- Trust the SRV-1 reverse proxy through its OCI/DRG address `10.11.1.11`.
- Publish only `wss://codex-acp.atius.com.br/gateway`; token authentication and
  device pairing remain mandatory.
- `10.100.100.0/24` is reserve fallback only. Never select it while the OCI/DRG
  path is available.
```

**Vault hydration pattern** (`modules/fork-sync/projects/codex-acp/runtime/hydrate-gateway-env.sh`, lines 4-10):
```bash
eval "$(/home/ubuntu/.local/bin/atius-vault-env codex-acp)"
: "${OPENCLAW_GATEWAY_TOKEN:?Vault profile codex-acp did not export OPENCLAW_GATEWAY_TOKEN}"

install -d -m 0700 /home/ubuntu/.config/openclaw
umask 077
printf 'OPENCLAW_GATEWAY_TOKEN=%s\n' "$OPENCLAW_GATEWAY_TOKEN" \
  > /home/ubuntu/.config/openclaw/gateway.env
```

**Service environment pattern** (`modules/fork-sync/projects/codex-acp/runtime/openclaw-codex-acp.service`, lines 9-21):
```ini
WorkingDirectory=/home/ubuntu
Environment=HOME=/home/ubuntu
Environment=CODEX_HOME=/home/ubuntu/.codex
Environment=HERMES_HOME=/home/ubuntu/.hermes
Environment=PATH=/home/ubuntu/.nvm/versions/node/v24.13.1/bin:/home/ubuntu/.local/bin:/home/ubuntu/.cargo/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=/home/ubuntu/.config/openclaw/gateway.env
ExecStart=/home/ubuntu/.nvm/versions/node/v24.13.1/bin/openclaw gateway run --port 18789
Restart=on-failure
RestartSec=5
TimeoutStartSec=180
TimeoutStopSec=30
KillMode=mixed
CPUQuota=80%
```

**Gateway contract pattern** (`modules/fork-sync/projects/codex-acp/runtime/openclaw.patch.json5`, lines 2-21, 23-33, 44-69):
```json5
gateway: {
  mode: "local",
  bind: "custom",
  customBindHost: "10.13.1.13",
  port: 18789,
  controlUi: {
    enabled: false,
    allowedOrigins: ["https://codex-acp.atius.com.br"],
  },
  auth: {
    mode: "token",
    rateLimit: {
      maxAttempts: 5,
      windowMs: 60000,
      lockoutMs: 300000,
      exemptLoopback: true,
    },
  },
  trustedProxies: ["127.0.0.1", "::1", "10.11.1.11"],
  allowRealIpFallback: false,
},
plugins: {
  allow: ["acpx"],
  entries: {
    acpx: {
      enabled: true,
      config: {
        permissionMode: "approve-all",
        nonInteractivePermissions: "fail",
        probeAgent: "codex",
        pluginToolsMcpBridge: true,
        openClawToolsMcpBridge: true,
```

```json5
acp: {
  enabled: true,
  dispatch: { enabled: true },
  backend: "acpx",
  defaultAgent: "codex",
  allowedAgents: ["codex"],
  maxConcurrentSessions: 2,
},
agents: {
  list: [
    {
      id: "codex",
      name: "Codex ACP ATIUS",
      workspace: "/home/ubuntu",
      runtime: {
        type: "acp",
        acp: {
          agent: "codex",
          backend: "acpx",
          mode: "persistent",
          cwd: "/home/ubuntu",
        },
      },
    },
  ],
}
```

Planner note:
These files pin gateway topology, auth source, proxy trust, and ACP dispatch.
Reuse them as the contract for authenticated Upgrade, gateway auth, approvals,
reconnect, and clean shutdown evidence.

---

### `48-wayland-browser-lifecycle.md` (test, streaming)

**Analogs:** `docs/operations/wayland-managed-runtime.md`, `docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md`, `.planning/phases/49-wayland-codex-headroom/49-VALIDATION.md`

**Runtime ownership and baseline pattern** (`docs/operations/wayland-managed-runtime.md`, lines 5-9, 35-42, 46-49):
```markdown
- runtime de `wayland.atius.com.br` é administrado a partir do `omni-srv-admin`
- source repo permanece `~/GitHub/wayland`
- listener atual do runtime: `0.0.0.0:25725`
- rebuild/reapply pós-update fica em `modules/fleet/scripts/`
- source/upstream lane fica em `modules/fork-sync/projects/wayland/sync.yaml`

- `https://wayland.atius.com.br/api/auth/status` -> `200`
- `http://127.0.0.1:25725/api/auth/status` no `atius-srv-3` -> `200`
- usuário WebUI `giovanni`; a senha é carregada do Vault profile `gsd-web-login`
  (`kv/atius/gsd/web-login`) e nunca deve ser registrada neste repo
- login público com a credencial hidratada do Vault -> sucesso
- `/api/auth/user` -> `200` com cookie de sessão
- validações de browser usam Chromium headless via Chrome DevTools; Playwright é
  fallback, não o caminho primário

preservar `Wayland -> codex-acp -> codex`; Headroom entra no transporte do
Codex, não substitui o adapter ACP.
```

**Browser lifecycle proof pattern** (`docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md`, lines 125-132):
```markdown
Only after ownership release, add a reversible Wayland-scoped selection for the
Headroom Codex home in the existing `codexConfig.ts` / `AcpAgentManager.ts`
launch seam or the ATIUS codex-acp wrapper. Do not make Headroom the fallback
for every shell Codex process on the host.

Canary one Wayland project first. Browser validation must use Chromium headless
through Chrome DevTools. Prove conversation creation, streaming, approvals,
cancel/resume, selected model/effort, and savings telemetry before broadening.
```

**Adjacent validation gate** (`.planning/phases/49-wayland-codex-headroom/49-VALIDATION.md`, lines 11-13, 18-20, 31-32):
```markdown
- codex-acp lifecycle remains protocol-compatible through Headroom.
- Wayland passes Chromium headless conversation/stream/approval/cancel/resume.
- Rollback restores native `Wayland -> codex-acp -> codex` with no lost task.

- 401/403, missing scope, incomplete WebSocket completion or reconnect loop.
- Requests route through proxy but eligible transforms/savings stay zero.
- ACP or Wayland requires bypassing approval/auth policy.

Chrome DevTools headless evidence, rollback rehearsal and Obsidian/GBrain notes.
```

---

### `48-router-cpu-verification.md` (test, batch)

**Analogs:** `docs/operations/resource-governor.md`, `modules/srv1-ops/configs/resource-governor.env`, `modules/srv1-ops/systemd/omni-builds.slice`, `modules/srv1-ops/scripts/build-cpu-guard-wrapper.sh`, `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md`

**Build profile command pattern** (`docs/operations/resource-governor.md`, lines 77-105, 121-126):
```markdown
| `builds` | `omni-builds.slice` | `podman build`, `make`, `cargo`, `bun build`, `next build` | `20% do CPU total do host` | `6G / 8G / swap 1G` | `80M read / 40M write` |

```bash
omni srv1-ops resources profiles
omni srv1-ops resources status
omni srv1-ops resources install --dry-run
omni srv1-ops resources install
omni srv1-ops resources logs
omni srv1-ops resources watchdog
```

```bash
omni srv1-ops resources run builds -- make -j2
omni srv1-ops resources run builds -- cargo build --release
omni srv1-ops resources run builds -- podman build -t meu-app .
```

`podman` rootless + cgroups v2 + `systemd-run --user` encaixa muito bem.

Recomendação:

```bash
omni srv1-ops resources run builds -- podman build -t my-image .
```
```

**Canonical CPU source pattern** (`docs/operations/resource-governor.md`, lines 168-183; `modules/srv1-ops/configs/resource-governor.env`, lines 38-46):
```markdown
limitado a 20% do CPU total do host. Em host com 4 vCPU, isso vira
`CPUQuota=80%` no cgroup (`cpu.max=80000 100000`). Em host com 8 vCPU, vira
`CPUQuota=160%`. O campo `RG_PROFILE_BUILDS_CPU_TOTAL_PCT=20` é a fonte de
verdade; `RG_PROFILE_BUILDS_CPU_QUOTA=20%` fica como fallback conservador para
instalações antigas.

Para tornar isso padrão em shells humanos e automações que chamam comandos
direto, instalar os wrappers:

```bash
modules/srv1-ops/scripts/install-build-cpu-guard.sh
```
```

```dotenv
RG_PROFILE_BUILDS_SLICE=omni-builds.slice
RG_PROFILE_BUILDS_CPU_TOTAL_PCT=20
RG_PROFILE_BUILDS_CPU_QUOTA=20%
RG_PROFILE_BUILDS_CPU_WEIGHT=100
RG_PROFILE_BUILDS_MEMORY_HIGH=6G
RG_PROFILE_BUILDS_MEMORY_MAX=8G
RG_PROFILE_BUILDS_MEMORY_SWAP_MAX=1G
RG_PROFILE_BUILDS_IO_READ_BW=80M
RG_PROFILE_BUILDS_IO_WRITE_BW=40M
```

**Slice/service fallback pattern** (`modules/srv1-ops/systemd/omni-builds.slice`, lines 5-13; `modules/srv1-ops/scripts/build-cpu-guard-wrapper.sh`, lines 201-228):
```ini
[Slice]
CPUQuota=20%
CPUWeight=100
MemoryHigh=6G
MemoryMax=8G
MemorySwapMax=1G
IOReadBandwidthMax=/dev/sda 80M
IOWriteBandwidthMax=/dev/sda 40M
IOWeight=100
TasksMax=8192
```

```bash
export OMNI_BUILD_CPU_GUARD_ACTIVE=1
if command -v python3 >/dev/null 2>&1 && cd "$repo" 2>/dev/null && python3 -m omni srv1-ops resources run builds -- "$real_cmd" "$@"; then
  exit 0
fi

# Fallback: preserve global build cap even sem omni CLI instalado.
if systemctl --user start omni-builds.slice >/dev/null 2>&1; then
  exec systemd-run --user --scope \
    --slice=omni-builds.slice \
    -p CPUWeight=100 \
    -p CPUQuota="${CPU_QUOTA}%" \
    -p MemoryMax=12G \
    "$real_cmd" "$@"
fi
```

**Router post-sync verification pattern** (`modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md`, lines 95-109):
```bash
go test ./common ./controller ./service/modelcatalog ./relay/common ./relay/channel/minimax ./relay/channel/deepseek ./relay/channel/codex ./service ./service/embeddinggovernor ./relay -count=1
python3 -m py_compile tools/clianything.py scripts/smoke-provider-consolidation.py scripts/smoke-embeddings.py
python3 -m unittest discover -s tests -p 'test_clianything*.py'
bin/clianything status --strict
bin/clianything providers --all
scripts/smoke-docs-links.sh
```

```bash
curl -sS -H "Authorization: Bearer $ATIUS_ROUTER_TOKEN" http://127.0.0.1:3000/v1/models | jq '.data[0].id, any(.data[]; has("pricing_version"))'
```

Planner note:
Use the Router test set above as the proof skeleton, but route any heavy Go/Cargo
verification through the build profile/wrapper. The exact `scripts/podman-admin.sh
profile-run` invocation mentioned in the Phase 48 checkpoint was not read
directly this turn and remains an execution-time gap.

---

## Shared Patterns

### Secret Handling
**Sources:** `AGENTS.md`, `modules/fork-sync/projects/codex-acp/runtime/hydrate-gateway-env.sh`
**Apply to:** Native OAuth proof, remote WSS lifecycle, Wayland login smokes
```bash
eval "$(/home/ubuntu/.local/bin/atius-vault-env codex-acp)"
: "${OPENCLAW_GATEWAY_TOKEN:?Vault profile codex-acp did not export OPENCLAW_GATEWAY_TOKEN}"
install -d -m 0700 /home/ubuntu/.config/openclaw
umask 077
```

Rule:
Document only Vault profile/path/variable names and redacted evidence. Never
persist raw tokens, Authorization headers, or prompt bodies.

### Runtime Chain Preservation
**Sources:** `docs/operations/wayland-managed-runtime.md`, `docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md`
**Apply to:** Local ACP, remote ACP, Wayland lifecycle
```text
Wayland -> codex-acp -> Codex CLI -> Headroom loopback proxy -> OpenAI
```

For Phase 48 specifically:
```text
Wayland -> codex-acp -> codex
```

Do not weaken this boundary by turning GSD skills into runtime agents or by
making proxy/gateway work substitute for native Codex OAuth.

### Stop Conditions
**Sources:** `docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md`, `.planning/phases/49-wayland-codex-headroom/49-VALIDATION.md`
**Apply to:** All five execution lanes
```markdown
- 401/403, token invalidation, missing scope, or incomplete completion/reconnect
- approval/auth policy weakened to make remote or browser paths pass
- active `/home/ubuntu/.codex` mutated unexpectedly
- secrets appear in journals, docs, logs, or transcripts
```

### CPU-Capped Verification
**Sources:** `docs/operations/resource-governor.md`, `modules/srv1-ops/configs/resource-governor.env`, `modules/srv1-ops/systemd/omni-builds.slice`
**Apply to:** Router deterministic tests and any heavy `cargo`/`go` follow-up
```bash
omni srv1-ops resources run builds -- <heavy-command>
```

Canonical budget:
```dotenv
RG_PROFILE_BUILDS_CPU_TOTAL_PCT=20
RG_PROFILE_BUILDS_CPU_QUOTA=20%
```

## Gaps / Unverified Paths

These appeared in Phase 48 context/checkpoint, but their concrete implementation
was not read directly in this turn. Planner should treat them as explicit gaps.

| Path / Command | Why It Matters | Gap |
|---|---|---|
| `./scripts/podman-admin.sh profile-run` | Live CPU-capped Router lane | Resolved on 2026-07-12: `verify-profile` proved `cpu.max=80000 100000`; run the focused Go suite directly through `profile-run` without nesting it inside `omni srv1-ops resources run builds` |
| Native `codex exec` prompt-smoke command | Required for renewable OAuth proof | Exact repo-pinned command is not documented in gathered repo analogs |
| Wayland source files `codexConfig.ts` / `AcpAgentManager.ts` | Mentioned in runbooks as the launch seam | They live in the external `wayland` fork, not in this repo |
| `scripts/codex-acp-atius-wrapper.sh` body | Critical runtime wrapper for local/remote ACP | Referred to by guards and OpenClaw config, but wrapper contents were not read this turn |

## Metadata

**Analog search scope:** `.planning/`, `docs/operations/`, `modules/fork-sync/projects/codex-acp/`, `modules/fork-sync/projects/atius-router/`, `modules/srv1-ops/`

**Files scanned from evidence already gathered:**
- `docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md`
- `docs/operations/wayland-managed-runtime.md`
- `.planning/phases/49-wayland-codex-headroom/49-VALIDATION.md`
- `modules/fork-sync/projects/codex-acp/UPSTREAM-SYNC-GUARDS.md`
- `modules/fork-sync/projects/codex-acp/runtime/hydrate-gateway-env.sh`
- `modules/fork-sync/projects/codex-acp/runtime/openclaw-codex-acp.service`
- `modules/fork-sync/projects/codex-acp/runtime/openclaw.patch.json5`
- `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md`
- `docs/operations/resource-governor.md`
- `modules/srv1-ops/configs/resource-governor.env`
- `modules/srv1-ops/systemd/omni-builds.slice`
- `modules/srv1-ops/scripts/build-cpu-guard-wrapper.sh`

**Pattern extraction date:** 2026-07-12
