---
phase: 47-internal-service-pki-closeout
plan: 01
status: complete
completed: 2026-07-12
requirements_completed: [PKI-01, PKI-02, PKI-03, PKI-04, PKI-05, PKI-06, PKI-07, PKI-08]
---

# Phase 47 Plan 01 Summary

Closed the service-listener portion of the ATIUS internal PKI. All four Linux
hosts rotated their service leafs from legacy `10.1.1.x` SANs to the canonical
OCI/DRG private IPs, and the Obsidian REST listener on `atius-srv-1` plus the
HashiCorp Vault listener on `atius-srv-3` now serve ATIUS-issued chains on the
canonical DRG endpoints.

Windows HTTPS from `GIOVANNI-W11-PC` passed against both listeners without
insecure flags. Backups were created before listener mutation and the closeout
was recorded in repo artifacts, Obsidian and GBrain without private material.
