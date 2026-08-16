---
name: hermes-cross-runtime-bridge
description: Use when a Hermes Agent running natively on Windows or inside WSL must identify both installations, inspect or invoke the peer runtime, access peer sessions, skills, memories, MCPs, config, logs, profiles, cron, plugins or source code, or synchronize selected resources without sharing mutable runtime state.
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [windows, linux]
metadata:
  hermes:
    tags: [hermes, windows, wsl, cross-runtime, sessions, skills, memory, mcp]
    related_skills: [hermes-agent, hermes-windows-wsl]
---

# Hermes Windows ↔ WSL Cross-Runtime Bridge

## Overview

Giovanni has two independent Hermes Agent installations on the same Windows 11 machine:

1. a native Windows runtime;
2. a Linux runtime inside WSL2, distro `Ubuntu-24.04`.

They are installations of the same product, but they are **not the same process, checkout, profile, session database, memory store, skill tree, scheduler, gateway or mutable runtime home**. The Windows filesystem is reachable from WSL through `/mnt/c`; the WSL filesystem is reachable from Windows through `\\wsl.localhost\Ubuntu-24.04`. Filesystem reachability does not turn the two runtimes into one.

This skill is symmetric: load the same skill from either runtime. First identify where it is running, then use the peer's native executable and native `HERMES_HOME` for operations that depend on runtime semantics.

For the machine-specific topology and copy-pasteable identity/discovery probes verified on 2026-07-19, read `references/verified-topology-and-probes.md`. Keep transient versions, hashes and counts in that reference; keep the body below focused on the durable cross-runtime method.

For synchronized default model/provider changes across both runtimes, including custom-provider fallback alignment and native resolution verification, read `references/default-model-provider-sync.md`.

For Giovanni's stable 3-environment YOLO topology on this Windows host (PowerShell 7/cmd.exe, MSYS2 Zsh, local WSL; but only 2 Hermes installs), also see `skill_view(name="hermes-yolo-three-env")`.

## When to Use

Use this skill when asked to:

- locate either Hermes installation or explain which one is active;
- inspect the other runtime's configuration, version, source checkout or health;
- find, list, export or search sessions from the other runtime;
- inspect, compare or deliberately synchronize skills and memories;
- inspect or test the other runtime's MCP configuration;
- inspect peer cron jobs, profiles, plugins, logs, gateway or Kanban state;
- run a one-shot prompt using the other Hermes installation;
- diagnose split-brain behavior between Windows and WSL;
- move selected, safe resources between the two environments.

Do not use live filesystem sharing as a shortcut. Cross-runtime access must preserve runtime ownership.

---

## 1. Non-Negotiable Runtime Boundary

### Canonical homes

| Runtime | Native `HERMES_HOME` | Source checkout | Native executable |
|---|---|---|---|
| Windows | `C:\Users\muniz\AppData\Local\hermes` | `C:\Users\muniz\AppData\Local\hermes\hermes-agent` | `C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe` |
| WSL | `/home/muniz/.hermes` | `/home/muniz/.hermes/hermes-agent` | `/home/muniz/.local/bin/hermes` |

The WSL venv entrypoint is also available under:

```text
/home/muniz/.hermes/hermes-agent/venv/bin/hermes
```

### Cross-filesystem views

| Viewed from | Peer runtime path |
|---|---|
| WSL → Windows | `/mnt/c/Users/muniz/AppData/Local/hermes` |
| Windows → WSL | `\\wsl.localhost\Ubuntu-24.04\home\muniz\.hermes` |

### Hard rule

Never set either runtime's `HERMES_HOME` to the other runtime's directory.

Forbidden examples:

```bash
# Never do this in WSL:
export HERMES_HOME=/mnt/c/Users/muniz/AppData/Local/hermes
```

```powershell
# Never do this in native Windows:
$env:HERMES_HOME='\\wsl.localhost\Ubuntu-24.04\home\muniz\.hermes'
```

Why: `state.db`, SQLite WAL/SHM files, locks, PID files, gateway state, logs, process metadata and caches are runtime-local. Sharing a mutable home across Win32 and WSL/DrvFS can corrupt databases and create cross-process races.

### Safe versus unsafe sharing

Safe to **copy deliberately**, after inspection and path normalization:

- `SKILL.md` and skill support files;
- `SOUL.md`;
- `memories/MEMORY.md` and `memories/USER.md` when explicit synchronization is intended;
- selected non-secret configuration settings;
- MCP definitions after translating native paths;
- exported, redacted session files;
- documentation and runbooks.

Never live-share or blindly overwrite:

- `state.db`, `state.db-wal`, `state.db-shm`;
- `*.lock`, `*.pid`;
- `gateway_state.json`;
- `logs/`, `cache/`, `sandboxes/`;
- `auth.json` or `.env` without an explicit credential migration task;
- active cron state, process registries or Kanban databases.

Completion criterion: every operation must target one explicit native runtime, and no command may make both runtimes write the same mutable store.

---

## 2. Identify the Current Runtime Before Acting

Do not infer the runtime from hostname: both report `GIOVANNI-W11-PC`.

### From a POSIX shell

```bash
printf 'HOME=%s\nHERMES_HOME=%s\nWSL_DISTRO_NAME=%s\n' \
  "$HOME" "${HERMES_HOME:-<unset>}" "${WSL_DISTRO_NAME:-<unset>}"
uname -a
command -v hermes
hermes --version
hermes config path
```

This is the WSL Hermes only when all key facts agree:

```text
WSL_DISTRO_NAME=Ubuntu-24.04
HERMES_HOME=/home/muniz/.hermes
config path=/home/muniz/.hermes/config.yaml
```

### From PowerShell 7

```powershell
$PSVersionTable.PSEdition
[Environment]::OSVersion.VersionString
$env:HERMES_HOME
Get-Command hermes -ErrorAction SilentlyContinue
hermes --version
hermes config path
```

The native Windows runtime must resolve to:

```text
C:\Users\muniz\AppData\Local\hermes
```

If shell environment inheritance is ambiguous, bypass PATH and call the canonical executable explicitly.

Completion criterion: record current runtime, current `HERMES_HOME`, config path, executable and version before any cross-runtime write.

---

## 3. Canonical Resource Map

For each relative path below, prefix the native runtime home from section 1.

| Resource | Relative path | Ownership / meaning |
|---|---|---|
| Main config | `config.yaml` | Local runtime behavior, models, MCP definitions, tools, gateway settings |
| Secrets | `.env` | Local secrets; never print or copy casually |
| Credential pools | `auth.json` | Local OAuth/API credential state; sensitive |
| Sessions | `state.db*` | Canonical local SQLite session/message store |
| Session artifacts | `sessions/` | Routing index, dumps and optional snapshots; not the canonical full history |
| Memories | `memories/MEMORY.md`, `memories/USER.md` | Built-in persistent memory loaded only by that runtime |
| Personality | `SOUL.md` | Runtime-local persona layer |
| Skills | `skills/<category>/<skill>/SKILL.md` | Runtime-local procedural knowledge tree |
| Skill telemetry | `skills/.usage.json`, when present | Curator usage/state metadata; local only |
| MCP definitions | `config.yaml:mcp_servers` | Local MCP clients and native stdio paths |
| MCP stderr/logs | `logs/mcp-stderr.log`, `logs/agent.log` | Local connection and tool lifecycle evidence |
| Gateway | `gateway_state.json`, `gateway.pid`, `gateway.lock` | Local gateway ownership/state |
| Cron | `cron/` | Local scheduler locks, outputs and heartbeat; jobs are runtime-local |
| Profiles | `profiles/<name>/` | Additional isolated profile homes, when present |
| Plugins | `plugins/` plus bundled repo plugins | Local user plugins and bundled plugin inventory |
| Source | `hermes-agent/` | Independent git checkout and venv for that runtime |
| Kanban | `kanban.db`, `kanban/` | Local board/runtime state unless explicitly configured otherwise |
| Logs | `logs/` | Local evidence only |
| Caches | `cache/`, model cache files | Disposable and runtime-local |

Important distinctions:

- `session_search` searches the current Hermes session database, not the peer runtime.
- `memory` reads/writes the current runtime's built-in memory, not the peer memory files.
- `skill_view` resolves the current runtime's skill tree, not the peer's.
- MCP tools loaded into a conversation belong to the current process. They are not handles to the peer process.
- GBrain and Obsidian are shared remote authoritative services when both configs point to the same ATIUS endpoints; their shared content is not proof that local Hermes state is shared.

---

## 4. Invoke Native Windows Hermes from WSL

Use native PowerShell 7 to set a Windows-native `HERMES_HOME` and call the Windows executable. This avoids inheriting `/home/muniz/.hermes` into the Win32 process.

Canonical prefix:

```bash
WIN_PWSH='/mnt/c/Program Files/PowerShell/7/pwsh.exe'
"$WIN_PWSH" -NoProfile -Command '
  $env:HERMES_HOME="C:\Users\muniz\AppData\Local\hermes"
  Set-Location "C:\Users\muniz"
  $h="C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
  & $h --version
  & $h config path
'
```

Do not use `C:\Users\muniz\.local\bin\hermes` from `cmd.exe` or PowerShell. That path is a POSIX shell wrapper intended for Git Bash/MSYS, not a native `.exe` command.

### Run arbitrary read-only peer CLI checks

```bash
"$WIN_PWSH" -NoProfile -Command '
  $env:HERMES_HOME="C:\Users\muniz\AppData\Local\hermes"
  Set-Location "C:\Users\muniz"
  $h="C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
  & $h profile list
  & $h mcp list
  & $h memory status
  & $h cron list --all
  & $h plugins list --plain --no-bundled
'
```

### Run a one-shot prompt in Windows Hermes

```bash
"$WIN_PWSH" -NoProfile -Command '
  $env:HERMES_HOME="C:\Users\muniz\AppData\Local\hermes"
  Set-Location "C:\Users\muniz"
  $h="C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
  & $h chat -q "Inspect the native Windows Hermes environment and report only verified facts."
'
```

This creates/updates a session in the Windows store. Use it only when peer-agent reasoning is actually needed; prefer direct read-only CLI inspection for inventory.

Completion criterion: the output's `Install directory` and `config path` must both be under `C:\Users\muniz\AppData\Local\hermes`.

---

## 5. Invoke WSL Hermes from Native Windows

Use `wsl.exe` with the explicit distro and user. Set WSL `HERMES_HOME` inside the Linux command, not in Windows environment variables.

### PowerShell canonical prefix

```powershell
wsl.exe -d Ubuntu-24.04 -u muniz -- bash -lc @'
export HERMES_HOME=/home/muniz/.hermes
export PATH=/home/muniz/.local/bin:/home/muniz/.hermes/hermes-agent/venv/bin:$PATH
hermes --version
hermes config path
'@
```

For automation where PowerShell here-string quoting is inconvenient:

```powershell
$cmd = 'export HERMES_HOME=/home/muniz/.hermes; export PATH=/home/muniz/.local/bin:/home/muniz/.hermes/hermes-agent/venv/bin:$PATH; hermes mcp list'
wsl.exe -d Ubuntu-24.04 -u muniz -- bash -lc $cmd
```

### Run a one-shot prompt in WSL Hermes

```powershell
$cmd = 'export HERMES_HOME=/home/muniz/.hermes; export PATH=/home/muniz/.local/bin:$PATH; cd /home/muniz; hermes chat -q "Inspect the WSL Hermes environment and report only verified facts."'
wsl.exe -d Ubuntu-24.04 -u muniz -- bash -lc $cmd
```

This writes to the WSL session store.

Completion criterion: output must show install directory `/home/muniz/.hermes/hermes-agent` and config `/home/muniz/.hermes/config.yaml`.

---

## 6. Cross-Runtime Session History

### Core rule

Never attach the current runtime directly to the peer `state.db`. Ask the peer's native Hermes CLI to query/export its own database.

### WSL querying its own history

```bash
HERMES_HOME=/home/muniz/.hermes hermes sessions stats
HERMES_HOME=/home/muniz/.hermes hermes sessions list --limit 20
```

### WSL querying Windows history

```bash
"$WIN_PWSH" -NoProfile -Command '
  $env:HERMES_HOME="C:\Users\muniz\AppData\Local\hermes"
  $h="C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
  & $h sessions stats
  & $h sessions list --limit 20
'
```

### Windows querying WSL history

```powershell
$cmd = 'export HERMES_HOME=/home/muniz/.hermes; export PATH=/home/muniz/.local/bin:$PATH; hermes sessions stats; hermes sessions list --limit 20'
wsl.exe -d Ubuntu-24.04 -u muniz -- bash -lc $cmd
```

### Safe transfer/search workflow

1. List peer sessions through the peer CLI.
2. Select a specific session ID or narrow filter.
3. Export through the peer CLI with `--redact`.
4. Write the export to a neutral transfer directory, not either live DB directory.
5. Read/search the exported text from the current runtime.

Example: export one WSL session for Windows to inspect:

```powershell
$cmd = 'export HERMES_HOME=/home/muniz/.hermes; export PATH=/home/muniz/.local/bin:$PATH; mkdir -p /mnt/c/Users/muniz/AppData/Local/hermes-cross-runtime/exports/wsl; hermes sessions export /mnt/c/Users/muniz/AppData/Local/hermes-cross-runtime/exports/wsl/session.jsonl --session-id SESSION_ID --format jsonl --redact'
wsl.exe -d Ubuntu-24.04 -u muniz -- bash -lc $cmd
```

Example: export one Windows session for WSL to inspect:

```bash
"$WIN_PWSH" -NoProfile -Command '
  $env:HERMES_HOME="C:\Users\muniz\AppData\Local\hermes"
  $h="C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
  $out="C:\Users\muniz\AppData\Local\hermes-cross-runtime\exports\windows\session.jsonl"
  New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
  & $h sessions export $out --session-id SESSION_ID --format jsonl --redact
'
```

Then read it in WSL at:

```text
/mnt/c/Users/muniz/AppData/Local/hermes-cross-runtime/exports/windows/session.jsonl
```

### Corruption rule

If the peer CLI reports `database disk image is malformed`, b-tree errors or invalid pages:

- stop querying the database repeatedly;
- do not run `VACUUM`, `optimize`, `repair`, delete or write operations in-place;
- preserve `state.db`, `state.db-wal` and `state.db-shm`;
- stop peer writers;
- recover only from a copy on the database's native filesystem;
- require `PRAGMA integrity_check = ok` before promotion.

Completion criterion: session evidence comes from the peer CLI or a verified redacted export, never from an actively written peer DB opened over `/mnt/c` or UNC.

---

## 7. Cross-Runtime Skills

### Inspect peer skills without installing them

From WSL, Windows skills are readable at:

```text
/mnt/c/Users/muniz/AppData/Local/hermes/skills/
```

From Windows, WSL skills are readable at:

```text
\\wsl.localhost\Ubuntu-24.04\home\muniz\.hermes\skills\
```

To inspect a peer skill, read its `SKILL.md` as a file. Do not assume local `skill_view` can resolve it.

### Compare a same-named skill

Compare content hashes or text before synchronization. The two trees may intentionally differ because Windows and WSL have different bundled/local provenance and path requirements.

WSL example:

```bash
sha256sum \
  /home/muniz/.hermes/skills/devops/SKILL_NAME/SKILL.md \
  /mnt/c/Users/muniz/AppData/Local/hermes/skills/devops/SKILL_NAME/SKILL.md
```

### Install or update a peer skill safely

- Create/update the skill in the target runtime's own `skills/` tree.
- Preserve the complete directory, including `references/`, `templates/`, `scripts/` and `assets/`.
- Validate frontmatter and linked files.
- Run `hermes skills list` using the target runtime's native executable.
- Start a new target session or run `/reload-skills`; current sessions cache skill discovery.

Never symlink the entire Windows and WSL skill roots together. Platform-specific skills and generated metadata may differ.

Completion criterion: both native `hermes skills list` commands show the intended skill as enabled, and the two installed copies have the expected hash.

---

## 8. Cross-Runtime Memory and Personality

Each runtime loads only its own:

```text
memories/MEMORY.md
memories/USER.md
SOUL.md
```

The current session's `memory` tool does not write the peer runtime.

### Read peer memory

Peer memory files may be read directly as text when needed for cross-session context. Treat them as private data. Do not paste the entire contents into logs, tickets, GBrain or Obsidian.

### Synchronize memory deliberately

Before copying:

1. read both versions;
2. compare semantics, not just timestamps;
3. merge durable facts only;
4. exclude temporary task progress and stale operational state;
5. back up the target file;
6. preserve target line endings and permissions;
7. never copy `.lock` files;
8. start a new peer session to load the result.

Do not blindly overwrite one runtime's memories with the other. Independent sessions may have learned distinct valid facts.

### Ask the peer runtime with its own memory loaded

When interpretation matters more than raw file inspection, run a one-shot peer Hermes prompt through section 4 or 5. That process will load its native memory, skills and config.

Completion criterion: any memory change is an explicit merge into one named target runtime, with no lock files copied and no secrets exposed.

---

## 9. Cross-Runtime MCPs

### Current baseline

Both runtimes currently configure these MCP clients; always re-run `hermes mcp list` because config can drift:

- `gbrain_http` — shared ATIUS remote GBrain service;
- `obsidian_http` — shared authoritative Obsidian REST/MCP service;
- `oci_admin_http` — shared ATIUS OCI Admin HTTP MCP;
- `chrome-devtools` — local stdio process, independently spawned per runtime;
- `ijfw-memory` — local stdio process with runtime-specific path syntax.

### Important semantics

- HTTP MCP services may point to the same authoritative remote data.
- Stdio MCP processes are not shared. Each Hermes starts its own child process.
- A tool loaded in the current conversation belongs to the current runtime's MCP client.
- To inspect/test the peer MCP, invoke the peer CLI:

```text
hermes mcp list
hermes mcp test <name>
```

using section 4 or 5.

### Path normalization

Typical equivalent path:

```text
Windows: C:\Users\muniz\.ijfw\mcp-server\src\server.js
WSL:    /mnt/c/Users/muniz/.ijfw/mcp-server/src/server.js
```

Do not copy a whole `config.yaml` and assume stdio paths remain valid. Translate only the target copy.

### Credentials

MCP bearer references belong in target `config.yaml` as environment references, such as:

```yaml
Authorization: Bearer ${ATIUS_MCP_TOKEN}
```

The value belongs in the target `.env`. Never materialize the token in the skill or command output. Hermes may display a safe redacted form such as `${ATIU...KEN}` or `***`; distinguish display redaction from a literal placeholder persisted in the YAML by inspecting safely without printing secrets.

Completion criterion: peer `hermes mcp test <name>` connects and discovers tools using the peer's native config and executable.

---

## 10. Profiles, Plugins, Cron, Gateway and Other State

### Profiles

Default homes above describe the `default` profile. Named profiles, when present, live under:

```text
<HERMES_HOME>/profiles/<name>/
```

Use the peer native CLI:

```text
hermes profile list
hermes --profile <name> ...
```

Do not assume a profile exists on both runtimes.

### Plugins

Plugin enablement and configuration are local. Inspect with:

```text
hermes plugins list --plain --no-bundled
```

Bundled plugins come from each independent source checkout; user plugins may live under the local home. Copying plugin config without matching code/dependencies is insufficient.

### Cron

Cron jobs, locks, output and scheduler heartbeat are runtime-local. Inspect through the peer CLI:

```text
hermes cron list --all
hermes cron status
```

A job in one runtime does not automatically exist or run in the other. Never copy `.jobs.lock`, `.tick.lock` or heartbeat files.

### Gateway ownership

The authoritative active gateway is currently the WSL system service. The native Windows default gateway is intentionally stopped. Re-verify with both native CLIs before relying on this statement.

Do not start the Windows gateway merely to inspect it. Two gateways using the same Telegram or other platform credentials can conflict, duplicate processing or flap-fight.

From Windows, inspect the WSL gateway:

```powershell
$cmd = 'export HERMES_HOME=/home/muniz/.hermes; export PATH=/home/muniz/.local/bin:$PATH; hermes gateway status'
wsl.exe -d Ubuntu-24.04 -u muniz -- bash -lc $cmd
```

### Source code and versions

The checkouts are independent and may have different upstream/local commits even when semantic versions match.

```bash
# WSL
git -C /home/muniz/.hermes/hermes-agent status --short --branch
git -C /home/muniz/.hermes/hermes-agent log -1 --oneline
```

```powershell
# Windows
git -C 'C:\Users\muniz\AppData\Local\hermes\hermes-agent' status --short --branch
git -C 'C:\Users\muniz\AppData\Local\hermes\hermes-agent' log -1 --oneline
```

Never copy source files between checkouts without diffing local modifications and tests.

---

## 11. Decision Guide: Read, Invoke, Export or Synchronize

| Goal | Correct method |
|---|---|
| Know peer version/path/status | Invoke peer native CLI |
| Read peer skill/runbook/log text | Read peer file read-only |
| Search peer sessions | Peer `sessions list/export`; search redacted export |
| Use peer memory/skills for reasoning | Run one-shot peer Hermes |
| Test peer MCP | Peer `hermes mcp test` |
| Compare configs | Read both with secrets redacted; normalize paths |
| Copy a skill | Copy complete skill dir deliberately; validate target |
| Merge memories | Semantic merge with backup; no lock files |
| Recover peer DB | Stop writers; native-filesystem copy; SQLite recovery workflow |
| Share live state | Never |

Use the least invasive method that preserves target ownership.

---

### Config synchronization policy

When comparing `config.yaml` between Windows local Hermes and a peer runtime like `atius-srv-1`, do a **selective sync**, never a blind copy.

Preferred sync targets when the goal is "bring over better operational limits":
- `agent.max_turns`
- `agent.api_max_retries`
- `goals.max_turns`
- `compression.hygiene_hard_message_limit`
- `logging.memory_monitor`

Do **not** blindly copy these without review:
- `approvals.mode` — remote runtimes may contain invalid scalar types like `false` instead of the string `off`; preserve the semantically correct local value.
- `memory.provider` — often runtime/database specific.
- `browser.engine` and `browser.allow_private_urls` — host/workflow specific.
- `session_reset.mode` — operational preference, not an objective improvement.
- `fallback_providers` and provider chains — depends on local credentials and routing goals.
- personality strings — often runtime/person-specific.

If you apply a selective sync:
1. read both configs completely enough to compare the relevant sections;
2. create a timestamped backup of the target `config.yaml` first;
3. patch only the selected keys;
4. explicitly preserve local values that are already better/correct;
5. validate the final target config with `hermes config check` and a readback summary;
6. record a short local report listing changed vs preserved keys.

Important pitfall discovered in this environment:
- `approvals.mode: false` on a peer runtime is **not** the right YOLO form when persisted intentionally; the canonical value to write is the string `off`.
- A peer file may still show `approvals.mode: off` and yet `yaml.safe_load()` / `load_config()` can surface it as boolean `False` because of YAML 1.1 coercion.
- Do not audit YOLO state from raw YAML alone. Verify the approval runtime too: `tools.approval._get_approval_mode()` may normalize that boolean back to semantic `off`, and `is_approval_bypass_active()` is the decisive functional check.
- If the target runtime already has `approvals.mode: 'off'`, preserve it and do not downgrade it to boolean `false`.
- Hooks are a separate layer; `approvals.mode=off` does not imply `HERMES_ACCEPT_HOOKS` / `hooks_auto_accept`. See `references/approval-mode-yaml-bool-audit.md`.

1. **Inherited `HERMES_HOME` crosses WSLInterop.** A Win32 process launched from WSL may inherit `/home/muniz/.hermes` and report the WSL checkout. Explicitly set the Windows home inside PowerShell before invoking `hermes.exe`.

2. **Hostname mistaken for runtime identity.** Both environments use `GIOVANNI-W11-PC`. Check OS, executable and config path.

3. **Opening peer SQLite directly.** Filesystem access is not database ownership. Use the peer CLI or a stopped, copied DB.

4. **Assuming `session_search`, `memory` or `skill_view` are cross-runtime.** They are scoped to the current Hermes home/profile.

5. **Blind config copy.** Windows and WSL stdio MCP paths differ. Copy selected settings, then normalize and test.

6. **Printing `.env` or `auth.json`.** Inspect existence, key names or redacted metadata only unless the user explicitly requests secret handling.

7. **Starting both gateways.** Shared messaging credentials can cause conflicts. Keep WSL authoritative unless the user explicitly migrates gateway ownership.

8. **Copying lock/PID/WAL files.** These are active runtime internals, never synchronization artifacts.

9. **Expecting a new skill in an existing session.** Use `/reload-skills` or start a fresh session in the target runtime.

10. **Treating equal semantic versions as equal code.** Compare git status and commit identity in both checkouts.

11. **Expecting `/reload-mcp` to load Python source changes.** It shuts down connections, re-reads `config.yaml`, reconnects servers and refreshes tool schemas, but it does not reload an already-imported `tools.mcp_tool` module. If MCP lifecycle code changed after the process started, exit and relaunch that Hermes CLI/gateway process. A whole-WSL restart is unnecessary unless the Linux environment itself is broken.

12. **Letting an idempotent shell guard preserve a cross-runtime home.** A nested WSL shell may inherit both `ATIUS_COMMON_ENV_LOADED=1` and a Windows `HERMES_HOME`; an early return can then skip the WSL boundary correction. Enforce `HERMES_HOME=/home/muniz/.hermes` and the WSL `WORKSPACE_STATE` before returning from the already-loaded path, and verify with a deliberately contaminated login-shell test.

---

## 13. Verification Checklist

Before reporting a cross-runtime operation complete:

- [ ] Current runtime identified by OS, executable, `HERMES_HOME` and config path.
- [ ] Target runtime named explicitly as Windows or WSL.
- [ ] Target native executable used for semantic operations.
- [ ] No target command inherited the wrong `HERMES_HOME`.
- [ ] No live mutable home, DB, lock, PID, WAL, gateway or cache was shared.
- [ ] Secrets were not printed, copied into prose or materialized in config.
- [ ] Session access used peer CLI or a verified redacted export.
- [ ] Skill synchronization included linked files and target discovery validation.
- [ ] Memory synchronization, if any, was semantic and backed up.
- [ ] MCP paths were normalized and tested in the target runtime.
- [ ] Gateway ownership remained singular.
- [ ] Source checkout differences and local modifications were preserved.
- [ ] Both runtime-specific validation commands returned real output.

## Quick Reference

```text
WINDOWS HOME
C:\Users\muniz\AppData\Local\hermes

WINDOWS EXE
C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe

WINDOWS AS SEEN FROM WSL
/mnt/c/Users/muniz/AppData/Local/hermes

WSL HOME
/home/muniz/.hermes

WSL EXE
/home/muniz/.local/bin/hermes

WSL AS SEEN FROM WINDOWS
\\wsl.localhost\Ubuntu-24.04\home\muniz\.hermes

WSL DISTRO / USER
Ubuntu-24.04 / muniz

SHARED REMOTE AUTHORITATIVE KNOWLEDGE
GBrain and Obsidian MCP services on ATIUS, when configured and healthy

NOT SHARED
sessions, memories, skills, config, credentials, MCP client processes,
cron, plugins, profiles, gateway state, source checkout, logs and caches
```
