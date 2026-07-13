---
phase: 45
status: complete
created: 2026-07-10
---

# Phase 45 Research

## Repo Findings

- `docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md` defines the DNS boundary: Cloudflare for public `atius.com.br`, internal DNS for machine names and private service identity.
- `docs/operations/ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md` is a useful runbook/reference, but phase execution order is now canonical only in `.planning/phases/45-internal-dns-drg-canonicalization/`.
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` is the canonical port map but still contains historical `10.1.1.x` sections that need classification.
- `inventory/hosts/*.yaml` now carries `oci_private_ip`; `vpn_ip` must be treated as fallback/reserve.
- `modules/fleet-control-plane/tools/validate_m004.py` should enforce `10.11.1.11:6432` for Linux fleet DB paths.
- Local `oci-admin/AGENTS.md` had a stale Vault endpoint at `10.100.100.3`; the current DRG endpoint is `10.13.1.13`.
- `workflow.plan_review_convergence` was missing from `.planning/config.json`; future convergence runs need it set to `true`.

## Cross-Session Findings

- `019f3c32-d2fd-70b0-b2f2-3c44709d2fa0`: `oci-admin` evidence shows OCI-primary service paths and router embeddings should prefer `10.21.1.21:3115`.
- `019f42b7-b699-7c03-965d-0aa081acc204`: W11 `wg100` was down, then revalidated; S23 still lacks handset-side outbound proof.
- `019f42bb-e564-7ca3-87b2-8573f3eb516e` and `019f4374-2b77-7361-9474-5a869abc6b33`: home-proxy/PPTP is residential edge fallback, not internal service DNS/DRG topology.
- `019f2ba1-1982-7c03-a17d-3ce28c589ac1`: Wayland should expose GSD as skills/commands, not runtime ACP agents. Track it as runtime tooling, not DNS scope.
- Remote `atius-srv-1` `omni-srv-admin` has uncommitted docs/inventory/Graphify changes. These must be explicitly merged or committed later; they cannot be assumed present locally through `git pull`.

## Obsidian / GBrain Findings

- Recent durable notes record that repo, Obsidian and GBrain must be updated together for service endpoint changes.
- The reliable GBrain fallback is source-vault write followed by `gbrain sync --full --no-embed` when embedding write-through fails.

## Live Findings To Revalidate In Execution

- SRV-1/SRV-2/SRV-3/Horistic resolver state may still contain legacy DNS references.
- Windows direct DRG reachability to `10.11.1.11` must be proven before removing the reserve exception.
- Cloudflare public records need review only for public hostnames; internal names should not be added there.

## Planning Consequence

Phase 45 must be executed before continuing Phase 42 edge publication or Phase 44 service PKI rollout, because both depend on stable internal name resolution and canonical service endpoints. The correct order is:

1. Converge planning/source-of-truth and AGENTS parity.
2. Get OCI-side proof from `oci-admin`.
3. Cut over internal DNS/resolvers and verify hostname ping.
4. Close fallback boundaries, remote dirty merge queue, Obsidian and GBrain.
