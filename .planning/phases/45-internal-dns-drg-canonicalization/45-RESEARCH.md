---
phase: 45
status: complete
created: 2026-07-10
---

# Phase 45 Research

## Repo Findings

- `docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md` defines the DNS boundary: Cloudflare for public `atius.com.br`, internal DNS for machine names and private service identity.
- `docs/operations/ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md` already has the execution waves for resolver cutover and drift detection.
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` is the canonical port map but still contains historical `10.1.1.x` sections that need classification.
- `inventory/hosts/*.yaml` now carries `oci_private_ip`; `vpn_ip` must be treated as fallback/reserve.
- `modules/fleet-control-plane/tools/validate_m004.py` should enforce `10.11.1.11:6432` for Linux fleet DB paths.

## Obsidian / GBrain Findings

- Recent durable notes record that repo, Obsidian and GBrain must be updated together for service endpoint changes.
- The reliable GBrain fallback is source-vault write followed by `gbrain sync --full --no-embed` when embedding write-through fails.

## Live Findings To Revalidate In Execution

- SRV-1/SRV-2/SRV-3/Horistic resolver state may still contain legacy DNS references.
- Windows direct DRG reachability to `10.11.1.11` must be proven before removing the reserve exception.
- Cloudflare public records need review only for public hostnames; internal names should not be added there.

## Planning Consequence

Phase 45 must be executed before continuing Phase 42 edge publication or Phase 44 service PKI rollout, because both depend on stable internal name resolution and canonical service endpoints.
