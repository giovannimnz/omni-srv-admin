# Omni Landscape CLI Integration

**Date:** 2026-06-26
**Scope:** Use Landscape self-hosted as the batch execution plane while keeping `omni-srv-admin` as the reviewed, versioned source of truth.

## Decision

`omni-srv-admin` owns script source, metadata, version and safety classification.

Landscape owns delivery, scheduling and activity tracking on registered Ubuntu machines.

The integration is exposed through:

```bash
PYTHONPATH=cli python3 -m omni landscape --help
```

## Authentication

Load credentials from the machine automation vault:

```bash
source <(atius-vault-env landscape)
```

Preferred self-hosted variables:

```bash
export OMNI_LANDSCAPE_ENDPOINT="https://landscape.atius.com.br/api/"
export OMNI_LANDSCAPE_ACCESS_KEY="..."
export OMNI_LANDSCAPE_SECRET_KEY="..."
```

Compatible fallback variables:

```bash
export LANDSCAPE_API_URI="https://landscape.atius.com.br/api/"
export LANDSCAPE_API_KEY="..."
export LANDSCAPE_API_SECRET="..."
```

Do not commit credentials. Do not use chat, GBrain, Obsidian, `.zshrc`, or
`.env` as the value source. They may point to the `landscape` Vault profile,
but automation must load the values through `atius-vault-env landscape`.

Current local self-hosted env file:

```bash
source ~/.config/omni/landscape-selfhost.env
```

This file is mode `0600` and contains only self-hosted credentials for `https://landscape.atius.com.br/api/`.

Optional REST v2 version inspection requires:

```bash
export OMNI_LANDSCAPE_JWT="..."
```

## Versioned Scripts

Manifest:

```text
modules/landscape-control-plane/scripts/manifest.json
```

Current scripts:

| ID | Risk | Purpose |
|---|---|---|
| `fleet-status` | read-only | Host identity, services, disk, memory, Ubuntu Pro and Landscape client status |
| `version-report` | read-only | Version inventory for important OS/runtime tools |
| `apt-upgrade-plan` | plan-only | `apt-get -s` simulation for upgrade/autoremove planning |
| `reboot-required` | read-only | Reboot-required state and package hints |

The Landscape script title is stable (`omni::<id>`). Changing code in the repo and running `scripts push/sync --yes` edits the existing Landscape script, allowing Landscape to track versions while Git remains the source of review.

## Commands

Local integration status:

```bash
PYTHONPATH=cli python3 -m omni landscape status
```

List registered Omni scope computers through Landscape:

```bash
PYTHONPATH=cli python3 -m omni landscape computers
```

List local script registry:

```bash
PYTHONPATH=cli python3 -m omni landscape scripts list
```

Plan sync without mutation:

```bash
PYTHONPATH=cli python3 -m omni landscape scripts sync
```

Apply sync to Landscape:

```bash
PYTHONPATH=cli python3 -m omni landscape scripts sync --yes
```

Plan a fleet run:

```bash
PYTHONPATH=cli python3 -m omni landscape run fleet-status --hosts all
```

Execute a fleet run:

```bash
PYTHONPATH=cli python3 -m omni landscape run fleet-status --hosts all --sync-script --yes
```

Run on selected hosts:

```bash
PYTHONPATH=cli python3 -m omni landscape run version-report --hosts atius-srv-1,atius-srv-3 --yes
```

Use custom Landscape query:

```bash
PYTHONPATH=cli python3 -m omni landscape run reboot-required --query 'tag:k3s' --yes
```

Raw legacy API call:

```bash
PYTHONPATH=cli python3 -m omni landscape api GetComputers --param 'query=hostname:atius-srv-1' --json
```

Non-`Get*` legacy API actions require `--yes`.

Monitor a submitted ActivityGroup:

```bash
PYTHONPATH=cli python3 -m omni landscape activities show 6
PYTHONPATH=cli python3 -m omni landscape activities show 6 --children
PYTHONPATH=cli python3 -m omni landscape activities recent --status undelivered
```

## Safety Rules

- `run` is plan-only unless `--yes` is provided.
- `scripts push/sync` is plan-only unless `--yes` is provided.
- Host selection is restricted to `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and `horistic-srv` unless a custom Landscape query is explicitly passed.
- Reboots, package mutation, PM2 restart, XRDP restart and K3s mutation should live in separate high-risk scripts with explicit approval gates.
- Script output may contain operational evidence; do not echo secrets from scripts.

## API Contract

The implementation uses the Landscape legacy API for script creation/edit/execution because Canonical documents that REST v2 script creation/modification still depends on the legacy API.

REST v2 is used only for optional version inspection when a JWT is available.

Self-hosted note:

- Landscape self-hosted 26.04 validates HMAC query signatures in received parameter order. The CLI preserves request order when signing.
- The local API rejected `interpreter` on `CreateScript`/`EditScript`; scripts use shebangs instead.
