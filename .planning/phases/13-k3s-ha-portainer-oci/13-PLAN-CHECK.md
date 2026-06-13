# Phase 13 Plan Check

**Date:** 2026-06-13
**Status:** PASSED WITH HUMAN GATES; EXECUTION CHECKPOINT BLOCKED BEFORE LIVE MUTATION 2026-06-13

## Checks

- Scope is clear: planning + future executable runbook, not live installation.
- User requirements captured:
  - branch created first
  - cluster nodes `ATIUS-SRV-1/2/3`
  - SRV-1/SRV-2/SRV-3 must be Ubuntu 24.04 before real setup
  - Portainer target `portainer.atius.com.br`
- Official-doc constraints included:
  - K3s embedded etcd needs 3+ server nodes and odd quorum
  - K3s ports restricted to private networking
  - PTP fallback full-mesh tracked as production-ready gate
  - OCI gates are per account because SRV-1/SRV-2/SRV-3 are in different OCI accounts
  - Portainer requires namespace `portainer`, RBAC and StorageClass
  - Portainer local storage requires node pinning in multi-node cluster
  - Cloudflare Tunnel token stored as Kubernetes Secret
  - OCI NSGs preferred for instance-specific firewalling
- Existing local risks included:
  - SRV-1/SRV-3 disk pressure
  - GDrive parallel backup rate-limit history
  - legacy Portainer on `docker.atius.com.br` is intentionally disabled and not an M005 dependency
  - Apache/port conflicts avoided by disabling Traefik/ServiceLB

## Required Human Gates

- SRV-1/SRV-2/SRV-3 are upgraded and postchecked on Ubuntu 24.04.4 LTS.
- Confirm OCI snapshots/backups per OCI account.
- Confirm OCI public-ingress closure in each OCI account and host firewall rules for `wg0`.
- Create/provide Cloudflare Tunnel token out-of-band.
- Complete or explicitly waive PTP fallback design before production-ready.
- Approve destructive K3s rollback if needed.

## Verdict

The node preflight is executable-ready after safe log cleanup, but live install
is still blocked until OCI snapshots/backups, OCI/host firewall rules, the
Cloudflare Tunnel token and human approval are confirmed. Do not install K3s
before those gates.
