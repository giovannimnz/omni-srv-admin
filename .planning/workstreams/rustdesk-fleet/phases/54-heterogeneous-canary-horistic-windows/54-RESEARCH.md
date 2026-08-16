---
phase: 54-heterogeneous-canary-horistic-windows
status: research-complete
---

# Phase 54 Research

## Pinned supply and topology

- Client version: RustDesk 1.4.9.
- Linux asset: ARM64 `.deb`, SHA256
  `ce62c996f14d33f3bbe3a330e953644a44bace7f05885a7953f7395d69fb49c0`.
- Windows asset: x86-64 `.msi`, SHA256
  `c87d2f4cef2a5acd6003b6507dcfbf5d5168a256db082cd90b54d35193224aaa`.
- Native rendezvous/relay endpoint: `rustdesk.atius.com.br`; Ops hostname is
  separate and must never be configured as the RustDesk client API server.
- Horistic server/client domains, resource budgets and rollback paths remain
  separate; a Horistic reboot is a deliberate joint outage.

## Reusable repository assets

- `validate_phase52.py` for strict pins, redaction and evidence precedence.
- `phase52_recovery.py` for bounded process, listener, SQLite and rollback
  primitives.
- `rustdesk-vault-provider` and the Vault helpers for ephemeral passwords.
- `probe-phase53-edge.py` / `.ps1` for external TCP/UDP and W11 private-first
  route evidence.
- `permission-profiles.json` for desired admin-maintenance and support-observe
  policy; unsupported native controls must be BLOCKED, never assumed.

## Missing implementation

No Phase 54 client installer, safe password wrapper, Linux/Windows collectors,
permission validator, fallback smoke runner or phase validator exists yet.
Those are explicit deliverables, not reasons to mark the canary ready.

## Empirical risks

- LightDM pre-login support is undocumented and must be proven empirically.
- RustDesk CLI password flags can leak through argv/history; use pipe/FD or
  ephemeral tmpfs and prove process/evidence redaction.
- W11 RDP/NLA previously reached guacd but desktop access failed due a missing
  correct Microsoft Account credential; do not infer RDP proof from SSH.
- Image, keyboard and mouse markers, direct/relay transport and capability
  negatives need headless evidence plus required human GUI checkpoints.

## Official RustDesk OSS cross-check (2026-07-23)

- The official OSS documentation separates `hbbs` (ID/rendezvous/signaling)
  from `hbbr` (relay traffic), matching the Phase 53 server/client boundary:
  https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/
- The official client configuration documents `Relay Server` as the `hbbr`
  endpoint and identifies TCP `21117` for relay; direct peer-to-peer remains
  the preferred path when hole punching succeeds:
  https://rustdesk.com/docs/en/self-host/client-configuration/
- The official relay guide confirms that additional `hbbr` nodes are for
  sessions where direct connectivity is unavailable and that the relay key
  pair must be shared with the authorized relay. This supports the
  direct-first/forced-relay evidence requirement without introducing a public
  RustDesk server:
  https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/relay/
