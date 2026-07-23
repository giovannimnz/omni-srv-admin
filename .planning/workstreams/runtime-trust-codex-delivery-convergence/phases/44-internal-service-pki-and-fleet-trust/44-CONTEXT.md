# Phase 44: Internal Service PKI and Fleet Trust - Context

**Gathered:** 2026-07-05
**Status:** Ready for planning
**Mode:** Operator requested plan-first, no live mutation in this step

<domain>

## Phase Boundary

Create an `omni-srv-admin` managed capability for internal TLS over the ATIUS
WireGuard VPN. The capability must issue one service certificate per managed
server, distribute trust to the other servers, and verify the full cross-host
trust matrix before it is considered complete.

Managed initial hosts:

| Host | SSH | VPN IP | Public IP | Notes |
|---|---|---:|---:|---|
| `atius-srv-1` | `ubuntu@10.1.1.1` | `10.1.1.1` | `137.131.190.161` | control plane / CA authority candidate |
| `atius-srv-2` | `ubuntu@10.1.1.2` | `10.1.1.2` | `129.148.47.32` | VPN hub / DNS |
| `atius-srv-3` | `ubuntu@10.1.1.3` | `10.1.1.3` | `136.248.126.12` | secrets / Vault / Keycloak related services |
| `horistic-srv` | `horistic@10.1.1.4` | `10.1.1.4` | `163.176.232.119` | k3s worker / TEI service |

</domain>

<decisions>

## Implementation Decisions

### D-01 - CA trust model

Use one internal service root/issuing CA chain for trust. Each server gets a
unique leaf cert/key. Do not install peer leaf certificates as root CAs.

### D-02 - Key locality

Generate host private keys on the target host where possible. Send only CSRs to
the signer on `atius-srv-1`; return signed certificates and chain files. CA
private keys stay root-only and outside Git.

### D-03 - Execution model

Use SSH only for controlled bootstrap and validation while the feature is being
built. The durable resource must be an Omni CLI/control-plane capability with
allowlisted local-agent commands.

### D-04 - Validation threshold

Completion requires a 4x4 trust matrix: local file verification on every host,
plus every source host validating every target host over a temporary HTTPS
endpoint using both VPN IP and a DNS SAN.

### D-05 - Scope fence

This phase creates the PKI resource and verifies generic HTTPS readiness. It
does not automatically switch TEI, Keycloak, Vault, Apache, XRDP, or other live
services to new ports/certs without service-specific gates.

</decisions>

<code_context>

## Existing Code Insights

- `inventory/hosts/*.yaml` is the source of host IDs, SSH targets, IPs and
  aliases.
- `cli/omni/fleet.py` already has `omni fleet` commands, inventory parsing,
  audit events and a local-agent allowlist path.
- `modules/fleet-control-plane/README.md` says durable mutation should go
  through `queue-update` plus target local agent, not broad direct SSH.
- `docs/operations/rdp-trust-pki.md` is the closest PKI precedent, but it is
  scoped to XRDP/RDP and Windows publisher trust.
- `docs/security/atius-secrets-vaults.md` is the secret-handling authority.

</code_context>

<specifics>

## Specific Ideas

- Add `omni fleet trust-pki` commands:
  - `plan`
  - `preflight`
  - `init-ca`
  - `issue-host`
  - `install-trust`
  - `verify`
  - `rollback-plan`
- Add `modules/fleet-pki/` scripts/templates/docs.
- Add inventory `pki.service_tls` fields for SANs and managed paths.
- Persist non-secret state as JSON under `/var/lib/omni-srv-admin/pki/state/`
  and audit summaries under `/home/<user>/.logs/fleet-pki/`.
- Keep raw keys and CA material under root-only paths:
  `/var/lib/omni-srv-admin/pki/private/` and
  `/etc/omni-srv-admin/tls/<host-id>/`.

</specifics>

<deferred>

## Deferred Ideas

- HashiCorp Vault PKI engine migration.
- mTLS enforcement for specific services.
- Automatic reverse proxy rollout for TEI or other apps.
- Windows trust-store import for this service CA.

</deferred>
