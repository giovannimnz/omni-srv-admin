---
spike: 001
name: fleet-service-pki-trust-matrix
type: standard
validates: "Given the four managed VPN servers, when Omni issues per-host leaf certs and distributes the CA, then every host can verify every other host by IP/DNS SAN without trusting peer leafs as roots"
verdict: PARTIAL
related: []
tags: [pki, tls, fleet, wireguard, validation]
---

# Spike 001: Fleet Service PKI Trust Matrix

## What This Validates

This spike validates the architecture, live preconditions and validation model
for an Omni-managed internal service PKI across `atius-srv-1`,
`atius-srv-2`, `atius-srv-3` and `horistic-srv`.

## Research

Existing context found:

- `docs/operations/rdp-trust-pki.md` already has a separate RDP/XRDP PKI and
  is not a generic service PKI.
- Obsidian note `60-LOGS/2026-07-02-rdp-trust-pki-fleet.md` confirms the RDP
  PKI used per-host leafs, SAN coverage, backups and trust-store validation.
- `docs/security/atius-secrets-vaults.md` confirms machine secrets must stay in
  HashiCorp Vault or root-only paths, not Git/logs.
- `modules/fleet-control-plane/README.md` confirms the durable execution model
  is allowlisted local agent execution, not broad direct SSH apply.

## Investigation Trail

- Graphify found prior certificate concern nodes and the RDP trust PKI docs.
- Inventory confirmed the four managed Linux hosts and their VPN/public IPs.
- Live read-only preflight on 2026-07-05 confirmed SSH, `sudo -n`,
  `openssl`, `update-ca-certificates` and NTP on all four hosts.
- No `/etc/omni-srv-admin/tls` directory exists yet on any of the four hosts.

## Results

Verdict: PARTIAL.

The approach is feasible, but the safe implementation should be a planned
phase before live mutation. The critical correction is that each server should
own a leaf certificate/key, while the trust store should receive the internal
CA chain. Installing each peer leaf as a root is incorrect and hard to revoke.
