---
phase: 43-codex-mcp-bootstrap-hardening
plan: 43-01
type: summary
status: complete
date: 2026-07-05
requirements:
  - CDX-01
  - CDX-02
  - CDX-03
  - CDX-06
---

# 43-01 Summary

## Changes

- Backed up the active Windows Codex runtime config before mutation.
- Split the default MCP baseline away from browser, OCI, Cloudflare,
  knowledge, and lab-only MCP surfaces.
- Kept the default `config.toml` lean with only the approved always-on MCP
  surface.
- Created named opt-in profile files under `C:\Users\muniz\.codex\`.
- Updated runtime docs so the operator path is explicit and reversible.

## Validation

```text
default baseline no longer auto-starts browser, OCI, Cloudflare, or lab MCPs
profile files exist for browser, cloud-ops, knowledge, oci, and lab
backup files created before mutation
```

## Backups

```text
C:\Users\muniz\.codex\backups\config.toml.phase43-mcp-split-20260705-073221.bak
```

## Residual Risk

- The lean split alone does not prove cold-start quality; timeout policy and
  failure classification are finalized in `43-02`.
- Profile activation behavior in Codex should still be validated through the
  dedicated smoke path rather than assumed from file presence.
