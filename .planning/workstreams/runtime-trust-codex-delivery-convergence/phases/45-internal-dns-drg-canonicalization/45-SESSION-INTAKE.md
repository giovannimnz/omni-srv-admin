---
phase: 45
artifact: session-intake
created: 2026-07-10
status: current
---

# 45 Session Intake

This file is the durable intake for the Codex sessions reviewed before the
Phase 45 replan. It is planning evidence only; execution remains owned by
`45-PLAN.md` and validation by `45-VALIDATION.md`.

## Sessions Reviewed

| Host | Session | Repo / area | Planning impact |
|---|---|---|---|
| `GIOVANNI-W11-PC` | `019f3c32-d2fd-70b0-b2f2-3c44709d2fa0` | `oci-admin` | OCI-primary route and DNS validation context. TEI/router embeddings must use `10.21.1.21:3115`; `10.100.100.4:3115` is reserve only. |
| `GIOVANNI-W11-PC` | `019f42b7-b699-7c03-965d-0aa081acc204` | `oci-admin` / W11 edge | W11 `wg100` was down and then revalidated. W11 can reach OCI target IPs through the `wg100` bridge; S23 still needs device-side outbound proof. |
| `atius-srv-1` | `019f42bb-e564-7ca3-87b2-8573f3eb516e` | `vpn-atius/home-proxy` plus remote `omni-srv-admin` docs | Home edge/PPTP is residential fallback only. BE3 reservations are W11 `192.168.1.8`, S20 `192.168.1.9` and S23 `192.168.1.10`; do not advertise `192.168.1.0/24` to DRG/wg100. |
| `atius-srv-1` | `019f4374-2b77-7361-9474-5a869abc6b33` | `vpn-atius/home-proxy` | BE3 VPN UI looked like client mode, not proven PPTP server. PPTP needs TCP `1723` plus GRE/protocol `47`; no promotion by assumption. |
| `GIOVANNI-W11-PC` | `019f2ba1-1982-7c03-a17d-3ce28c589ac1` | Wayland on `atius-srv-3` | GSD profiles must be exposed as skills/commands (`$gsd-*` or slash command), not as runtime `acp.customAgents`. This is a parallel runtime dependency, not a DNS blocker. |

## Canonical Conclusions

- `10.1.1.0/24` no longer exists operationally. It can remain only in
  historical evidence, closed phase artifacts, or explicit cleanup manifests.
- DRG/OCI private IPs are the primary server-to-server service plane:
  `10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`.
- `10.100.100.0/24` / `wg100` is reserve fallback and edge access for W11/S23;
  it is not the canonical service plane.
- Internal DNS must let operators use short names such as `ping atius-srv-1`
  and receive the DRG/OCI private IP whenever the client is on a path that can
  reach the DRG plane.
- `oci-admin` owns the OCI-side proof: DRG route tables, VCN/subnet naming,
  security lists/NSGs, private IP attachment evidence, and bridge evidence for
  edge clients.
- `omni-srv-admin` owns the service/inventory/source-of-truth proof: host
  inventory, resolver cutover runbooks, internal DNS contract, drift checks,
  and durable Obsidian/GBrain closeout.
- `home-proxy` owns residential BE3/PPTP exploration. It must not become
  internal service DNS authority or DRG route authority without a separate
  routed-site phase.
- Wayland on `atius-srv-3` is relevant to operator runtime consistency, but it
  should not block Phase 45 DNS unless it changes Codex/GSD skill invocation or
  documentation surfaces used during execution.

## Checkout State Observed

- Local `omni-srv-admin` and remote `atius-srv-1` checkout were both on
  `e7119af` / `origin/main`.
- Remote `atius-srv-1` checkout had uncommitted docs/inventory/Graphify changes
  from the home-proxy/PPTP work. Those are not pullable through Git until they
  are committed or manually merged.
- Local `omni-srv-admin/AGENTS.md` and remote `AGENTS.md` are semantically
  aligned on DRG primary host identity and Vault at `10.13.1.13`; normalized
  comparison showed only trailing whitespace/newline drift.
- Local `oci-admin/AGENTS.md` had a stale Vault endpoint on `10.100.100.3`; it
  was corrected in this replan to `10.13.1.13` with explicit DRG-primary notes.
- 2026-07-10 follow-up: S23 `10.100.100.6` came back online. Server-side
  evidence from `atius-srv-1` showed fresh handshake, `ping` 3/3, and TCP
  `8022` open, but SSH authentication into Termux still failed from Windows, so
  device-side outbound proof remains open. See `45-S23-EDGE-VALIDATION.md`.
