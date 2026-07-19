# Spike Manifest

## Idea

De-risk fleet architecture changes with bounded, evidence-producing spikes.
The current frontier is low-latency Wayland development across the OCI/DRG
fleet: canonical FreeIPA names, encrypted persistent SSH, and the correct
boundary between owner-local sessions and the existing NFS workspace tree.
The earlier internal service PKI spike remains part of this portfolio.

## Requirements

- Do not install peer leaf certificates as trusted roots. Trust is anchored on
  an internal CA; peer leafs may be copied only as public evidence/pinning
  material.
- Private keys stay out of Git, `.planning`, Obsidian, GBrain, logs and shell
  history.
- Any live trust-store change needs backup, dry-run output and post-change
  matrix validation.
- OCI/DRG addresses and lowercase `*.atius.internal` FQDNs are canonical;
  `10.100.100.0/24` remains reserve/edge transport only.
- No benchmark may weaken host-key checking, accept a key through TOFU, expose
  credentials, or install a plaintext remote shell.
- Compare cold and warm SSH separately and report distributions; a single best
  sample is not an SLA.
- Preserve the NFS workspace tree until an owner-local remote mode proves
  equivalent project discovery, editing, reconnect and rollback behavior.

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | fleet-service-pki-trust-matrix | standard | Given the four managed VPN servers, when Omni issues per-host leaf certs and distributes the CA, then every host can verify every other host by IP/DNS SAN without trusting peer leafs as roots | PARTIAL | pki,tls,fleet,wireguard,validation |
| 002 | freeipa-fqdn-ssh-multiplexing | standard | Canonical `*.atius.internal` owner-host execution can reach a 13-15 ms warm target through encrypted persistent SSH with fail-closed host-key trust | PARTIAL | wayland,ssh,freeipa,drg,latency |
| 003 | wayland-nfs-vs-owner-local | standard | Persistent owner-local sessions make complete removal of the srv-3 NFS workspace tree beneficial and safe | INVALIDATED | wayland,nfs,remote-development,resources |
| 004 | plaintext-transport-negative-gate | standard | Disabling SSH encryption or adopting HPN NoneSwitch materially improves interactive command latency on the ATIUS DRG | INVALIDATED | ssh,security,hpn,latency |
