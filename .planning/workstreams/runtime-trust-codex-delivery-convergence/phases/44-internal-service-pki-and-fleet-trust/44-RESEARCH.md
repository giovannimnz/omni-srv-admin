# Phase 44 Research: Internal Service PKI and Fleet Trust

## Inputs Consulted

- Graphify query: `certificate`
- Repo docs:
  - `docs/operations/rdp-trust-pki.md`
  - `docs/security/atius-secrets-vaults.md`
  - `docs/fleet/inventory-model.md`
  - `modules/fleet-control-plane/README.md`
- Inventory:
  - `inventory/hosts/atius-srv-1.yaml`
  - `inventory/hosts/atius-srv-2.yaml`
  - `inventory/hosts/atius-srv-3.yaml`
  - `inventory/hosts/horistic-srv.yaml`
- Obsidian:
  - `60-LOGS/2026-07-02-rdp-trust-pki-fleet.md`
- GBrain:
  - Omni fleet inventory/control-plane notes
  - RDP PKI fleet note
  - ATIUS fleet network/port map note

## Findings

### Existing RDP PKI is not the service PKI

The fleet already has an RDP/XRDP trust PKI with a Windows root, publisher cert,
per-host XRDP leafs, CRL/AIA endpoint and signed `.rdp` files. That solves a
different trust problem and should not be reused as the generic internal
service CA.

### Trust should be CA-based, not leaf-as-root

The operator's desired peer model is valid if interpreted as:

- each host has its own leaf certificate/key;
- every host trusts the common ATIUS internal service CA;
- peer public leafs can be copied for inventory/pinning evidence;
- peer leafs are not installed as trusted roots.

### Private-key movement should be minimized

The safest operational model is target-side key generation:

1. target host creates private key and CSR;
2. CSR is copied to the signing authority on `atius-srv-1`;
3. `atius-srv-1` signs the CSR with the internal service CA;
4. signed leaf/chain is copied back to the target;
5. CA chain is installed into all trust stores.

This means host private keys never need to leave their owning host.

### Live preflight baseline

Read-only SSH preflight on 2026-07-05:

| Host | SSH user | sudo -n | OpenSSL | update-ca-certificates | NTP | TLS dir |
|---|---|---|---|---|---|---|
| `atius-srv-1` | `ubuntu` | ok | `OpenSSL 3.0.13` | present | yes | absent |
| `atius-srv-2` | `ubuntu` | ok | `OpenSSL 3.0.13` | present | yes | absent |
| `atius-srv-3` | `ubuntu` | ok | `OpenSSL 3.0.13` | present | yes | absent |
| `horistic-srv` | `horistic` | ok | `OpenSSL 3.0.13` | present | yes | absent |

### Durable execution should use the Omni agent model

The control-plane contract already says the durable path is:

`queue-update -> TbUpdatePlans -> target host omni-fleet-agent -> allowlisted local command`

Direct SSH is acceptable for bootstrap/probing while the feature is being built,
but the final resource must register allowlisted commands and audit results.

## Recommended Design

- CA authority host: `atius-srv-1`.
- Root/issuing CA name: `ATIUS VPN Service Root CA` and
  `ATIUS VPN Service Issuing CA 2026`.
- Leaf profile: `serverAuth,clientAuth`, `CA:FALSE`, SAN required, CN ignored
  for validation.
- Managed root CA path on every host:
  `/usr/local/share/ca-certificates/atius-vpn-service-root-ca.crt`
- Managed leaf path on each host:
  `/etc/omni-srv-admin/tls/<host-id>/server.crt.pem`
  `/etc/omni-srv-admin/tls/<host-id>/server.key.pem`
  `/etc/omni-srv-admin/tls/<host-id>/chain.crt.pem`
- Validation endpoint:
  temporary `openssl s_server` bound to the host VPN IP on a free high port,
  removed after validation.

## Open Risks

- Revocation publication for internal service certs is not yet defined.
- Service-specific TLS rollout still needs per-service adapters.
- HashiCorp Vault PKI would be stronger long-term but adds scope and an
  operational dependency.
- The repo has a dirty worktree; phase work must stage/select files carefully.
