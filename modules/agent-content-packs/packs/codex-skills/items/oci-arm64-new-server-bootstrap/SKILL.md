---
name: oci-arm64-new-server-bootstrap
description: Bootstrap and validate a new ATIUS OCI Ubuntu ARM64 server without copying secrets or misconfiguring subnet routing.
---

# OCI ARM64 New Server Bootstrap

Use for a new ATIUS OCI Ubuntu 24.04 ARM64 server.

## Read first

- `docs/runbooks/atius-srv4-bootstrap.md`
- `modules/xrdp-abnt2/README.md`
- `modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`
- `inventory/hosts/atius-srv-4.yaml` when applicable

## Workflow

1. Wait for cloud-init and package installers to finish.
2. Use `oci_admin_http` reads to verify instance/VNIC, security list, NSG,
   gateway and the effective subnet route table.
3. Require a route through the IGW before testing public SSH. Test TCP first,
   then compare public/private-key fingerprints before troubleshooting auth.
4. Create `~/GitHub` and `~/GitHub/containers`; copy only a clean Git source.
5. Install the ARM64 baseline and verify Podman rootless.
6. Invoke `$xrdp-abnt2-fleet` for the keyboard stage after installing the
   `omni` CLI; keep the transactional guard's backup evidence and validate the
   timer. Treat the new host as its own bootstrap target, not as evidence that
   it participated in an earlier fleet rollout.
7. Add the host inventory and publish sanitized evidence to GBrain/Obsidian.

## Never do

- Copy private keys, Vault material, `.env`, agent state, PM2 dumps or caches.
- Reuse an ingress route table as a subnet egress table.
- Add a host to K3s, DRG, Vault or a production container role merely because
  another server has that role.
