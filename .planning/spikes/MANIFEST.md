# Spike Manifest

## Idea

Build an Omni-managed internal service PKI so every managed Linux server has
its own TLS leaf certificate and every peer can trust services over the
WireGuard VPN.

## Requirements

- Do not install peer leaf certificates as trusted roots. Trust is anchored on
  an internal CA; peer leafs may be copied only as public evidence/pinning
  material.
- Private keys stay out of Git, `.planning`, Obsidian, GBrain, logs and shell
  history.
- Any live trust-store change needs backup, dry-run output and post-change
  matrix validation.

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | fleet-service-pki-trust-matrix | standard | Given the four managed VPN servers, when Omni issues per-host leaf certs and distributes the CA, then every host can verify every other host by IP/DNS SAN without trusting peer leafs as roots | PARTIAL | pki,tls,fleet,wireguard,validation |
