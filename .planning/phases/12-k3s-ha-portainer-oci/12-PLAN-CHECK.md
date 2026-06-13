# Phase 12 Plan Check

**Date:** 2026-06-13
**Status:** PASSED WITH HUMAN GATES

## Checks

- Scope is clear: planning + future executable runbook, not live installation.
- User requirements captured:
  - branch created first
  - cluster nodes `ATIUS-SRV-1/2/3`
  - SRV-1 must be Ubuntu 24.04 before real setup
  - Portainer target `portainer.atius.com.br`
- Official-doc constraints included:
  - K3s embedded etcd needs 3+ server nodes and odd quorum
  - K3s ports restricted to private networking
  - Portainer requires namespace `portainer`, RBAC and StorageClass
  - Portainer local storage requires node pinning in multi-node cluster
  - Cloudflare Tunnel token stored as Kubernetes Secret
  - OCI NSGs preferred for instance-specific firewalling
- Existing local risks included:
  - SRV-1/SRV-3 disk pressure
  - GDrive parallel backup rate-limit history
  - existing Portainer on `docker.atius.com.br`
  - Apache/port conflicts avoided by disabling Traefik/ServiceLB

## Required Human Gates

- Confirm SRV-1 is upgraded and postchecked on Ubuntu 24.04.
- Confirm OCI snapshots/backups.
- Confirm OCI NSG/Security List rules.
- Create/provide Cloudflare Tunnel token out-of-band.
- Approve destructive K3s rollback if needed.

## Verdict

The plan is executable after the SRV-1 Ubuntu 24.04 gate passes. Do not run the
installation while SRV-1 remains Ubuntu 22.04 or while SRV-3 has insufficient
disk space.
