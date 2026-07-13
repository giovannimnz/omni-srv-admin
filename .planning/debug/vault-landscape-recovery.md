---
status: resolved
trigger: "Landscape HashiCorp Secrets fails against retired 10.1.1.3; HashiCorp Vault is sealed after restart; Cloudflare profile cannot hydrate."
created: 2026-07-12
updated: 2026-07-13
---

# Vault and Landscape Recovery

## Symptoms

- Expected: Landscape reads and edits its allowlisted HashiCorp records; `codex-cloud-ops` hydrates Cloudflare credentials only into its child process.
- Actual: Landscape AppRole login targets `https://10.1.1.3:8202` and receives connection refused. Vault at `https://10.13.1.13:8202` is reachable but reports `sealed=true` and HTTP 503.
- Reproduction: Open a HashiCorp-backed Landscape Secrets record, or run a Vault-backed automation profile.
- Timeline: Vault container restarted at 2026-07-12 06:08 UTC; current service remains sealed.

## Current Focus

- hypothesis: Confirmed. Stale bridge endpoint and missing post-start unseal were independent blockers.
- test: Backup, unseal, bridge readdress, controlled service restart, AppRole read/edit smoke, and Vault-backed Cloudflare launcher smoke.
- expecting: Met. Vault health HTTP 200 with `sealed=false`; bridge read/edit succeeds; Cloudflare profile exports expected names only.
- next_action: Monitor the next scheduled backup; no active recovery action remains.

## Evidence

- timestamp: 2026-07-12; Vault health at 10.13.1.13 reports initialized=true, sealed=true, version=2.0.3.
- timestamp: 2026-07-12; Landscape error targets retired 10.1.1.3:8202.
- timestamp: 2026-07-13; fresh Raft snapshot created and Vault recovered to initialized=true, sealed=false, HTTP 200.
- timestamp: 2026-07-13; Landscape bridge changed to https://10.13.1.13:8202 with an in-container backup; AppRole read all 16 records and a no-op edit preserved data.
- timestamp: 2026-07-13; post-start unseal drop-in survived a controlled Vault service restart.

## Resolution

- root_cause: The bridge retained a retired VPN endpoint, and the Vault service had no post-start unseal hook.
- fix: Readdressed the bridge, added an idempotent root-only post-start unseal guard, and moved optional MCPs out of the Codex baseline.
- verification: Vault health, all bridge records, no-op edit, Cloudflare profile/launcher, baseline smoke, and browser preflight passed without printing secrets.
