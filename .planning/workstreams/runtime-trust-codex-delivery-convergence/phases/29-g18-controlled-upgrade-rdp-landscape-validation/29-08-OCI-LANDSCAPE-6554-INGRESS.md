# Phase 29 evidence - OCI ingress for Landscape TCP 6554

Date: 2026-06-25

## Outcome

Public TCP `6554` for Landscape self-hosted is now open on the SRV1 public edge.

External probe result:

- `137.131.190.161:6554`: open

## Implementation

The Codex MCP config was updated from the existing Hermes OCI MCP definitions.

Backup:

- `/home/ubuntu/.codex/config.toml.bak-oci-mcp-20260625T183816Z`

Because the current Codex thread did not hot-load the new `mcp__oci_*` namespaces, the same backend configured by the MCP was used directly:

- OCI CLI binary: `/home/ubuntu/GitHub/oracle-oci-mcp/src/oci-api-mcp-server/.venv/bin/oci`
- OCI profile: `atius1`
- OCI config: `/home/ubuntu/.oci/config`

No OCI credentials, private keys, tokens, or secrets were copied into repo artifacts.

## Network change

Created a scoped OCI Network Security Group:

- Display name: `landscape-6554-srv1`
- VCN: SRV1 VCN
- Attached only to SRV1 primary VNIC
- Rule: stateful ingress TCP `6554` from `0.0.0.0/0`

SRV1 VNIC:

- Public IP: `137.131.190.161`
- Private IP: `10.0.0.38`
- VNIC display name: `AtiusCapital1`

Local SRV1 forwarding already existed before this OCI change:

- `landscape-6554-proxy.socket`: active
- Listener: `0.0.0.0:6554`
- Backend target: `10.1.1.3:6554`

SRV3 backend listener:

- `0.0.0.0:6554`: listening through LXD proxy to the Landscape container

## Backups/evidence

OCI evidence backup:

- `/home/ubuntu/.backups/oci-landscape-6554-20260625T184450Z`

Files in the backup include VNIC before/after state, NSG creation output, rule JSON, and rule list output.

## Validation

External TCP check:

```text
try_1=open
```

SRV1 local listener:

```text
landscape-6554-proxy.socket active
LISTEN 0.0.0.0:6554
```

SRV3 backend listener:

```text
LISTEN *:6554
```

## Residual notes

This resolves the OCI ingress blocker for Landscape TCP `6554`.

Phase 29 still has other blockers:

- Microsoft RDP interactive login must be reconfirmed by the operator.
- Pending apt packages remain for `xrdp`, Chromium, and SRV2 phased packages.
- Observability remains yellow.
- SRV1/SRV2 root disks remain at 86%.
