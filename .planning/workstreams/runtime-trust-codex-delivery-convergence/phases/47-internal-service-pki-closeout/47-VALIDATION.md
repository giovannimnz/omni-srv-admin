# Phase 47 Validation - Internal Service PKI Closeout

## Required Proof

- Existing CA/leaf backups and rollback commands verified before mutation.
- CA state and private keys remain root-only and absent from repo/logs.
- Each host leaf has expected SANs, EKUs, `CA:FALSE`, owner and mode.
- Four local `openssl verify` checks pass.
- Twelve cross-host HTTPS checks pass with hostname/IP verification and code 0.
- Obsidian and Vault serve issued ATIUS chains on canonical DRG endpoints.
- Windows verifies both services without `-k` or disabled TLS verification.
- Focused PKI tests, inventory validation and `git diff --check` pass.

## Stop Conditions

- Missing or unverified backup.
- SAN mismatch, expired chain, wrong key ownership, or leaf installed as root CA.
- Any service cannot reload cleanly or health check regresses.
- A client requires insecure verification after the change.

## Rollback

Restore the per-service certificate/config backup, reload the affected service,
remove only the newly installed trust material by fingerprint, run
`update-ca-certificates`, and repeat native health checks.

## Completion Evidence

Redacted audit JSON, fingerprint matrix, Windows/Linux command results, service
health, backup paths and Obsidian/GBrain closeout.
